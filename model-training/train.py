import os
import json
import torch
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer,
    DataCollatorForLanguageModeling, EarlyStoppingCallback
)
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType
import redis
from rq import Worker, Queue
from supabase import create_client, Client
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import wandb
import yaml

# Metrics.
TRAINING_JOBS = Counter('training_jobs_total', 'Total training jobs', ['status'])
TRAINING_DURATION = Histogram('training_duration_seconds', 'Training duration')
TRAINING_LOSS = Gauge('training_loss', 'Current training loss')
VALIDATION_LOSS = Gauge('validation_loss', 'Current validation loss')

@dataclass
class TrainingConfig:
    model_name: str = "microsoft/DialoGPT-small"
    max_length: int = 512
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 5e-5
    num_epochs: int = 3
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 100
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    min_quality_score: float = 0.6

class ModelTrainer:
    def __init__(self):
        self.setup_logging()
        self.setup_supabase()
        self.setup_redis()
        self.load_config()
        
        # Initialize wandb for experiment tracking
        wandb.init(
            project="indra-ai", 
            name=f"training-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            config=self.config.__dict__
        )
        
        # Start metrics server
        start_http_server(8003)
        
    def setup_logging(self):
        logger.add("/app/logs/training.log", rotation="100 MB", retention="30 days")
        
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
        
    def load_config(self):
        """Load training configuration"""
        config_path = '/app/config/training.yaml'
        
        # Default config
        self.config = TrainingConfig()
        
        # Override with environment variables
        self.config.model_name = os.getenv('MODEL_NAME', self.config.model_name)
        self.config.batch_size = int(os.getenv('BATCH_SIZE', self.config.batch_size))
        self.config.learning_rate = float(os.getenv('LEARNING_RATE', self.config.learning_rate))
        self.config.num_epochs = int(os.getenv('TRAINING_EPOCHS', self.config.num_epochs))
        
        # Load from file if exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
        
    def load_training_data(self, source: Optional[str] = None) -> Dataset:
        """Load training data from Supabase"""
        logger.info(f"Loading training data for source: {source}")
        
        query = self.supabase.table('processed_content').select(
            'cleaned_content, tokens, quality_score'
        ).eq('is_training_ready', True).gte('quality_score', self.config.min_quality_score)
        
        if source:
            query = query.eq('source', source)
            
        result = query.order('quality_score', desc=True).execute()
        
        if not result.data:
            raise ValueError("No training data found")
            
        # Prepare dataset
        texts = []
        for item in result.data:
            texts.append(item['cleaned_content'])
            
        logger.info(f"Loaded {len(texts)} training samples")
        
        # Create HuggingFace dataset
        dataset = Dataset.from_dict({"text": texts})
        return dataset
        
    def tokenize_function(self, examples):
        """Tokenize examples for training"""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors="pt"
        )
        
    def prepare_model_and_tokenizer(self) -> Tuple[AutoModelForCausalLM, AutoTokenizer]:
        """Prepare model and tokenizer"""
        logger.info(f"Loading model: {self.config.model_name}")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            
        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
        
        # Apply LoRA if configured
        if self.config.use_lora:
            logger.info("Applying LoRA configuration")
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
            )
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()
            
        return model, tokenizer
        
    def create_data_collator(self, tokenizer):
        """Create data collator for language modeling"""
        return DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,  # We're doing causal LM, not masked LM
        )
        
    def create_training_job_record(self, source: Optional[str] = None) -> str:
        """Create training job record in database"""
        job_data = {
            'job_name': f"IndraAI Training - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'model_name': self.config.model_name,
            'source': source,
            'config': json.dumps(self.config.__dict__),
            'status': 'started',
            'started_at': datetime.utcnow().isoformat()
        }
        
        result = self.supabase.table('training_jobs').insert(job_data).execute()
        
        if result.data:
            return result.data[0]['id']
        else:
            raise Exception(f"Failed to create training job record: {result}")
            
    def update_training_job_record(self, job_id: str, updates: Dict):
        """Update training job record"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        result = self.supabase.table('training_jobs').update(updates).eq('id', job_id).execute()
        
        if not result.data:
            logger.error(f"Failed to update training job {job_id}: {result}")
        
    @TRAINING_DURATION.time()
    def train_model(self, source: Optional[str] = None) -> str:
        """Train the model"""
        logger.info("Starting model training")
        TRAINING_JOBS.labels(status='started').inc()
        
        # Create training job record
        job_id = self.create_training_job_record(source)
        
        try:
            # Load data
            dataset = self.load_training_data(source)
            
            # Prepare model and tokenizer
            model, tokenizer = self.prepare_model_and_tokenizer()
            self.tokenizer = tokenizer
            
            # Tokenize dataset
            tokenized_dataset = dataset.map(
                self.tokenize_function,
                batched=True,
                remove_columns=dataset.column_names
            )
            
            # Split dataset
            train_size = int(0.9 * len(tokenized_dataset))
            train_dataset = tokenized_dataset.select(range(train_size))
            eval_dataset = tokenized_dataset.select(range(train_size, len(tokenized_dataset)))
            
            # Create data collator
            data_collator = self.create_data_collator(tokenizer)
            
            # Training arguments
            output_dir = f"/app/models/indra-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            training_args = TrainingArguments(
                output_dir=output_dir,
                overwrite_output_dir=True,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                per_device_eval_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                learning_rate=self.config.learning_rate,
                warmup_steps=self.config.warmup_steps,
                logging_steps=self.config.logging_steps,
                save_steps=self.config.save_steps,
                eval_steps=self.config.eval_steps,
                evaluation_strategy="steps",
                save_strategy="steps",
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                report_to="wandb",
                fp16=torch.cuda.is_available(),
                dataloader_pin_memory=False,
                remove_unused_columns=False,
            )
            
            # Custom trainer with metrics logging
            class CustomTrainer(Trainer):
                def log(self, logs: Dict[str, float]) -> None:
                    super().log(logs)
                    if "train_loss" in logs:
                        TRAINING_LOSS.set(logs["train_loss"])
                    if "eval_loss" in logs:
                        VALIDATION_LOSS.set(logs["eval_loss"])
            
            # Initialize trainer
            trainer = CustomTrainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                data_collator=data_collator,
                callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
            )
            
            # Update job status
            self.update_training_job_record(job_id, {'status': 'training'})
            
            # Train model
            logger.info("Starting training...")
            trainer.train()
            
            # Save final model
            final_model_path = f"/app/models/indra-final-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            trainer.save_model(final_model_path)
            tokenizer.save_pretrained(final_model_path)
            
            # Save training config
            config_path = os.path.join(final_model_path, "training_config.json")
            with open(config_path, 'w') as f:
                json.dump(self.config.__dict__, f, indent=2)
                
            # Update job record
            self.update_training_job_record(job_id, {
                'status': 'completed',
                'model_path': final_model_path,
                'completed_at': datetime.utcnow().isoformat()
            })
                
            logger.info(f"Training completed. Model saved to: {final_model_path}")
            TRAINING_JOBS.labels(status='completed').inc()
            
            # Trigger model update via API
            try:
                import requests
                api_host = os.getenv('API_HOST', 'api')
                api_port = os.getenv('API_PORT', '8000')
                api_url = f"http://{api_host}:{api_port}/model/update"
                
                response = requests.post(api_url, params={'model_path': final_model_path})
                if response.status_code == 200:
                    logger.info(f"Successfully triggered model update on API: {api_url}")
                else:
                    logger.error(f"Failed to trigger model update. Status: {response.status_code}, Response: {response.text}")
            except Exception as e:
                logger.error(f"Error triggering model update via API: {e}")
            
            return final_model_path
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            self.update_training_job_record(job_id, {
                'status': 'failed',
                'error_message': str(e),
                'failed_at': datetime.utcnow().isoformat()
            })
            TRAINING_JOBS.labels(status='failed').inc()
            raise
            
    def run_worker(self):
        """Run as RQ worker"""
        logger.info("Starting model training worker")
        worker = Worker([self.queue], connection=self.redis_client)
        worker.work()

if __name__ == "__main__":
    trainer = ModelTrainer()
    
    # Check if running as worker or standalone
    if os.getenv('RUN_AS_WORKER', 'true').lower() == 'true':
        trainer.run_worker()
    else:
        # Train model with all available data
        try:
            model_path = trainer.train_model()
            logger.info(f"Training completed successfully: {model_path}")
        except Exception as e:
            logger.error(f"Training failed: {e}")
