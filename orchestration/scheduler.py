import os
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import redis
from rq import Queue
from rq_scheduler import Scheduler
from supabase import create_client, Client
from loguru import logger
from prometheus_client import Counter, Gauge, start_http_server

# Metrics
SCHEDULED_JOBS = Counter('scheduled_jobs_total', 'Total scheduled jobs', ['job_type'])
ACTIVE_JOBS = Gauge('active_jobs', 'Currently active jobs', ['job_type'])
FAILED_JOBS = Counter('failed_jobs_total', 'Total failed jobs', ['job_type'])

class OrchestrationScheduler:
    def __init__(self):
        self.setup_logging()
        self.setup_supabase()
        self.setup_redis()
        self.setup_scheduler()
        
        # Start metrics server
        start_http_server(8004)
        
    def setup_logging(self):
        logger.add("/app/logs/scheduler.log", rotation="100 MB", retention="30 days")
        
    def setup_supabase(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase: Client = create_client(url, key)
        
    def setup_redis(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        password = os.getenv('REDIS_PASSWORD')
        
        self.redis_client = redis.from_url(
            redis_url,
            password=password,
            decode_responses=True
        )
        
        # Initialize queues
        self.scraping_queue = Queue('scraping', connection=self.redis_client)
        self.processing_queue = Queue('processing', connection=self.redis_client)
        self.training_queue = Queue('training', connection=self.redis_client)
        
    def setup_scheduler(self):
        self.scheduler = Scheduler(connection=self.redis_client)
        
    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        try:
            # Get scraped content stats
            scraped_result = self.supabase.table('scraped_content').select('source, created_at').execute()
            scraped_stats = {}
            
            if scraped_result.data:
                for item in scraped_result.data:
                    source = item['source']
                    if source not in scraped_stats:
                        scraped_stats[source] = {'total': 0, 'recent': 0}
                    scraped_stats[source]['total'] += 1
                    
                    # Check if recent (last 24 hours)
                    created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                    if created_at > datetime.now() - timedelta(hours=24):
                        scraped_stats[source]['recent'] += 1
            
            # Get processed content stats
            processed_result = self.supabase.table('processed_content').select('source, is_training_ready, quality_score').execute()
            processed_stats = {}
            
            if processed_result.data:
                for item in processed_result.data:
                    source = item['source']
                    if source not in processed_stats:
                        processed_stats[source] = {'total': 0, 'training_ready': 0, 'quality_scores': []}
                    
                    processed_stats[source]['total'] += 1
                    if item['is_training_ready']:
                        processed_stats[source]['training_ready'] += 1
                    processed_stats[source]['quality_scores'].append(item['quality_score'])
                
                # Calculate average quality scores
                for source in processed_stats:
                    scores = processed_stats[source]['quality_scores']
                    processed_stats[source]['avg_quality'] = sum(scores) / len(scores) if scores else 0.0
                    del processed_stats[source]['quality_scores']
            
            return {
                'scraped': scraped_stats,
                'processed': processed_stats,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
            
    def should_trigger_scraping(self, source: str) -> bool:
        """Determine if scraping should be triggered for a source"""
        try:
            # Get recent scraping activity
            cutoff_time = datetime.utcnow() - timedelta(hours=6)
            
            result = self.supabase.table('scraped_content').select('id').eq('source', source).gte('created_at', cutoff_time.isoformat()).execute()
            
            recent_count = len(result.data) if result.data else 0
            
            # Trigger scraping if less than 10 documents in last 6 hours
            return recent_count < 10
            
        except Exception as e:
            logger.error(f"Error checking scraping trigger for {source}: {e}")
            return False
            
    def should_trigger_processing(self, source: str) -> bool:
        """Determine if processing should be triggered for a source"""
        try:
            # Get unprocessed content count
            scraped_result = self.supabase.table('scraped_content').select('id').eq('source', source).execute()
            processed_result = self.supabase.table('processed_content').select('original_id').eq('source', source).execute()
            
            scraped_ids = {item['id'] for item in scraped_result.data} if scraped_result.data else set()
            processed_ids = {item['original_id'] for item in processed_result.data} if processed_result.data else set()
            
            unprocessed_count = len(scraped_ids - processed_ids)
            
            # Trigger processing if more than 5 unprocessed documents
            return unprocessed_count > 5
            
        except Exception as e:
            logger.error(f"Error checking processing trigger for {source}: {e}")
            return False
            
    def should_trigger_training(self) -> bool:
        """Determine if training should be triggered"""
        try:
            # Check for training-ready content
            result = self.supabase.table('processed_content').select('id').eq('is_training_ready', True).execute()
            
            training_ready_count = len(result.data) if result.data else 0
            auto_train_threshold = int(os.getenv('AUTO_TRAIN_THRESHOLD', 1000))
            
            # Check last training time
            training_result = self.supabase.table('training_jobs').select('created_at').order('created_at', desc=True).limit(1).execute()
            
            if training_result.data:
                last_training = datetime.fromisoformat(training_result.data[0]['created_at'].replace('Z', '+00:00'))
                time_since_last = datetime.utcnow() - last_training
                
                # Don't train more than once per day
                if time_since_last < timedelta(hours=24):
                    return False
            
            return training_ready_count >= auto_train_threshold
            
        except Exception as e:
            logger.error(f"Error checking training trigger: {e}")
            return False
            
    def schedule_scraping_job(self, source: str):
        """Schedule a scraping job"""
        try:
            job = self.scraping_queue.enqueue(
                'data_collection.scraper.WebScraper.scrape_source',
                source,
                job_timeout='1h'
            )
            
            SCHEDULED_JOBS.labels(job_type='scraping').inc()
            logger.info(f"Scheduled scraping job for {source}: {job.id}")
            
        except Exception as e:
            logger.error(f"Error scheduling scraping job for {source}: {e}")
            FAILED_JOBS.labels(job_type='scraping').inc()
            
    def schedule_processing_job(self, source: str):
        """Schedule a processing job"""
        try:
            job = self.processing_queue.enqueue(
                'data_processing.processor.DataProcessor.process_source_data',
                source,
                job_timeout='2h'
            )
            
            SCHEDULED_JOBS.labels(job_type='processing').inc()
            logger.info(f"Scheduled processing job for {source}: {job.id}")
            
        except Exception as e:
            logger.error(f"Error scheduling processing job for {source}: {e}")
            FAILED_JOBS.labels(job_type='processing').inc()
            
    def schedule_training_job(self):
        """Schedule a training job"""
        try:
            job = self.training_queue.enqueue(
                'model_training.train.ModelTrainer.train_model',
                job_timeout='6h'
            )
            
            SCHEDULED_JOBS.labels(job_type='training').inc()
            logger.info(f"Scheduled training job: {job.id}")
            
        except Exception as e:
            logger.error(f"Error scheduling training job: {e}")
            FAILED_JOBS.labels(job_type='training').inc()
            
    def monitor_and_schedule(self):
        """Main monitoring and scheduling logic"""
        logger.info("Running monitoring and scheduling cycle")
        
        # Get system stats
        stats = self.get_system_stats()
        
        # Check each source for scraping needs
        sources = ['tech_news', 'ai_research', 'programming_blogs']
        
        for source in sources:
            # Check scraping
            if self.should_trigger_scraping(source):
                self.schedule_scraping_job(source)
                
            # Check processing
            if self.should_trigger_processing(source):
                self.schedule_processing_job(source)
                
        # Check training
        if self.should_trigger_training():
            self.schedule_training_job()
            
        # Update metrics
        for queue_name, queue in [
            ('scraping', self.scraping_queue),
            ('processing', self.processing_queue),
            ('training', self.training_queue)
        ]:
            ACTIVE_JOBS.labels(job_type=queue_name).set(len(queue))
            
        logger.info("Monitoring cycle completed")
        
    def cleanup_old_jobs(self):
        """Clean up old completed jobs"""
        try:
            # Clean up jobs older than 7 days
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            
            # Clean up old training jobs
            self.supabase.table('training_jobs').delete().lt('created_at', cutoff_time.isoformat()).execute()
            
            # Clean up old API usage logs (keep 30 days)
            usage_cutoff = datetime.utcnow() - timedelta(days=30)
            self.supabase.table('api_usage').delete().lt('created_at', usage_cutoff.isoformat()).execute()
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
    def run_scheduler(self):
        """Run the scheduler"""
        logger.info("Starting orchestration scheduler")
        
        # Schedule regular monitoring
        schedule.every(30).minutes.do(self.monitor_and_schedule)
        
        # Schedule daily cleanup
        schedule.every().day.at("02:00").do(self.cleanup_old_jobs)
        
        # Run initial monitoring
        self.monitor_and_schedule()
        
        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    scheduler = OrchestrationScheduler()
    scheduler.run_scheduler()
