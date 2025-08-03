import os
import re
import json
import pickle
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import nltk
import spacy
from transformers import AutoTokenizer
import redis
from rq import Worker, Queue
from supabase import create_client, Client
from loguru import logger
from prometheus_client import Counter, Histogram, start_http_server
import textstat

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)

# Metrics
DOCUMENTS_PROCESSED = Counter('documents_processed_total', 'Total documents processed', ['source', 'status'])
PROCESSING_DURATION = Histogram('processing_duration_seconds', 'Time spent processing documents')

@dataclass
class ProcessingStats:
    total_documents: int
    processed_documents: int
    filtered_documents: int
    average_quality_score: float
    total_tokens: int

class DataProcessor:
    def __init__(self):
        self.setup_logging()
        self.setup_supabase()
        self.setup_redis()
        self.setup_nlp()
        
        # Start metrics server
        start_http_server(8002)
        
    def setup_logging(self):
        logger.add("/app/logs/processor.log", rotation="100 MB", retention="30 days")
        
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
        self.queue = Queue(connection=self.redis_client)
        
    def setup_nlp(self):
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model not found. Please install: python -m spacy download en_core_web_sm")
            raise
            
        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
        
        # NLTK components
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
        
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
            
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*$$$$,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\!\?\,\;\:\-$$$$]', '', text)
        
        return text.strip()
        
    def extract_features(self, text: str) -> Dict:
        """Extract various features from text"""
        doc = self.nlp(text)
        
        # Basic statistics
        word_count = len([token for token in doc if not token.is_space])
        sentence_count = len(list(doc.sents))
        
        # Token statistics
        tokens = self.tokenizer.encode(text, max_length=2048, truncation=True)
        token_count = len(tokens)
        
        # Language features
        pos_tags = [token.pos_ for token in doc if not token.is_space]
        named_entities = [(ent.text, ent.label_) for ent in doc.ents]
        
        # Readability metrics
        flesch_score = textstat.flesch_reading_ease(text)
        avg_sentence_length = word_count / max(sentence_count, 1)
        
        # Vocabulary diversity
        unique_words = len(set([token.lemma_.lower() for token in doc if not token.is_stop and token.is_alpha]))
        vocabulary_diversity = unique_words / max(word_count, 1)
        
        return {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'token_count': token_count,
            'avg_sentence_length': avg_sentence_length,
            'pos_tags': pos_tags,
            'named_entities': named_entities,
            'tokens': tokens,
            'flesch_score': flesch_score,
            'vocabulary_diversity': vocabulary_diversity
        }
        
    def calculate_quality_score(self, text: str, features: Dict) -> float:
        """Calculate quality score for the text"""
        score = 0.0
        
        # Length score (prefer medium-length texts)
        word_count = features['word_count']
        if 100 <= word_count <= 2000:
            score += 0.25
        elif 50 <= word_count < 100 or 2000 < word_count <= 3000:
            score += 0.15
        elif word_count < 50:
            score += 0.05
        else:
            score += 0.1
            
        # Sentence structure score
        avg_sentence_length = features['avg_sentence_length']
        if 10 <= avg_sentence_length <= 25:
            score += 0.2
        elif 5 <= avg_sentence_length < 10 or 25 < avg_sentence_length <= 35:
            score += 0.1
            
        # Readability score
        flesch_score = features.get('flesch_score', 0)
        if 30 <= flesch_score <= 70:  # Reasonably readable
            score += 0.2
        elif 70 < flesch_score <= 90:  # Easy to read
            score += 0.15
        elif flesch_score > 90:  # Very easy
            score += 0.1
            
        # Vocabulary diversity score
        diversity = features.get('vocabulary_diversity', 0)
        if diversity > 0.6:
            score += 0.15
        elif diversity > 0.4:
            score += 0.1
            
        # Named entity score
        if features['named_entities']:
            score += 0.1
            
        # Grammar and structure score (simplified)
        pos_tags = features['pos_tags']
        if pos_tags:
            noun_ratio = pos_tags.count('NOUN') / len(pos_tags)
            verb_ratio = pos_tags.count('VERB') / len(pos_tags)
            if 0.15 <= noun_ratio <= 0.4 and 0.1 <= verb_ratio <= 0.3:
                score += 0.1
                
        return min(score, 1.0)
        
    def tokenize_for_training(self, text: str) -> List[int]:
        """Tokenize text for training"""
        tokens = self.tokenizer.encode(
            text,
            max_length=2048,
            truncation=True,
            padding=False
        )
        return tokens
        
    @PROCESSING_DURATION.time()
    def process_document(self, doc_id: int, source: str, content: str) -> bool:
        """Process a single document"""
        try:
            # Clean text
            cleaned_content = self.clean_text(content)
            
            if len(cleaned_content.strip()) < 50:  # Skip very short content
                DOCUMENTS_PROCESSED.labels(source=source, status='too_short').inc()
                return False
                
            # Extract features
            features = self.extract_features(cleaned_content)
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(cleaned_content, features)
            
            # Tokenize for training
            tokens = self.tokenize_for_training(cleaned_content)
            
            # Determine if ready for training (quality threshold)
            is_training_ready = quality_score >= 0.6 and len(tokens) >= 100
            
            # Save processed content
            result = self.supabase.table('processed_content').insert({
                'source': source,
                'original_id': doc_id,
                'cleaned_content': cleaned_content,
                'tokens': json.dumps(tokens),
                'word_count': features['word_count'],
                'sentence_count': features['sentence_count'],
                'quality_score': quality_score,
                'flesch_score': features.get('flesch_score', 0),
                'vocabulary_diversity': features.get('vocabulary_diversity', 0),
                'is_training_ready': is_training_ready,
                'processed_at': datetime.utcnow().isoformat()
            }).execute()
            
            if result.data:
                status = 'success' if is_training_ready else 'low_quality'
                DOCUMENTS_PROCESSED.labels(source=source, status=status).inc()
                return True
            else:
                logger.error(f"Failed to save processed content: {result}")
                DOCUMENTS_PROCESSED.labels(source=source, status='error').inc()
                return False
                
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            DOCUMENTS_PROCESSED.labels(source=source, status='error').inc()
            return False
            
    def process_source_data(self, source: str) -> ProcessingStats:
        """Process all data from a specific source"""
        logger.info(f"Processing data from source: {source}")
        
        # Get unprocessed content from the source
        scraped_data = self.supabase.table('scraped_content').select('id, content').eq('source', source).execute()
        
        if not scraped_data.data:
            logger.warning(f"No scraped data found for source: {source}")
            return ProcessingStats(0, 0, 0, 0.0, 0)
            
        # Get already processed IDs
        processed_data = self.supabase.table('processed_content').select('original_id').eq('source', source).execute()
        processed_ids = {item['original_id'] for item in processed_data.data} if processed_data.data else set()
        
        # Filter unprocessed documents
        unprocessed_docs = [doc for doc in scraped_data.data if doc['id'] not in processed_ids]
        
        total_documents = len(unprocessed_docs)
        processed_count = 0
        
        logger.info(f"Found {total_documents} unprocessed documents from {source}")
        
        for doc in unprocessed_docs:
            if self.process_document(doc['id'], source, doc['content']):
                processed_count += 1
                
        # Calculate statistics
        stats_data = self.supabase.table('processed_content').select(
            'quality_score, word_count, is_training_ready'
        ).eq('source', source).execute()
        
        if stats_data.data:
            quality_scores = [item['quality_score'] for item in stats_data.data]
            word_counts = [item['word_count'] for item in stats_data.data]
            training_ready_count = sum(1 for item in stats_data.data if item['is_training_ready'])
            
            stats = ProcessingStats(
                total_documents=total_documents,
                processed_documents=processed_count,
                filtered_documents=training_ready_count,
                average_quality_score=np.mean(quality_scores) if quality_scores else 0.0,
                total_tokens=sum(word_counts) if word_counts else 0
            )
        else:
            stats = ProcessingStats(total_documents, processed_count, 0, 0.0, 0)
        
        logger.info(f"Processing completed for {source}: {processed_count}/{total_documents} documents processed")
        
        # If we have enough training-ready data, queue training job
        auto_train_threshold = int(os.getenv('AUTO_TRAIN_THRESHOLD', 1000))
        if stats.filtered_documents >= auto_train_threshold:
            self.queue.enqueue('model_training.train.train_model', source)
            logger.info(f"Queued training job for {source} ({stats.filtered_documents} training-ready documents)")
            
        return stats
        
    def run_worker(self):
        """Run as RQ worker"""
        logger.info("Starting data processing worker")
        worker = Worker([self.queue], connection=self.redis_client)
        worker.work()

if __name__ == "__main__":
    processor = DataProcessor()
    
    # Check if running as worker or standalone
    if os.getenv('RUN_AS_WORKER', 'true').lower() == 'true':
        processor.run_worker()
    else:
        # Process all sources
        sources = ['tech_news', 'ai_research', 'programming_blogs']
        for source in sources:
            try:
                processor.process_source_data(source)
            except Exception as e:
                logger.error(f"Error processing source {source}: {e}")
