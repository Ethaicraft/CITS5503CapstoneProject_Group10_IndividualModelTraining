# -*- coding: utf-8 -*-
"""GPT2_attempt1.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Q84k0_9oh__Mza2TzDOTJPZTahiDz1-P

# **GPT**

# 1. Install required libraries
"""

!pip install transformers datasets scikit-learn

import numpy as np
import pandas as pd
from transformers import GPT2Tokenizer, GPT2ForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
import torch
import matplotlib.pyplot as plt
import seaborn as sns

"""# 2. Load the dataset"""

# Upload the dataset
from google.colab import files
uploaded = files.upload()

train_df = pd.read_csv('HateSpeechDetection_test_Clean.csv')
test_df = pd.read_csv('HateSpeechDetection_train_Clean.csv')

# Convert to Hugging Face Dataset format
train_dataset = Dataset.from_pandas(train_df)
test_dataset = Dataset.from_pandas(test_df)

"""# 3. Preprocess the data using GPT-2 tokenizer"""

# Load GPT-2 tokenizer
tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
tokenizer.pad_token = tokenizer.eos_token  # Use eos_token as padding token

# Preprocessing function to tokenize text
def preprocess_function(examples):
    return tokenizer(examples['prompt'], padding="max_length", truncation=True, max_length=128)

# Apply preprocessing to train and test datasets
tokenized_train = train_dataset.map(preprocess_function, batched=True)
tokenized_test = test_dataset.map(preprocess_function, batched=True)

# Rename the 'label' column to 'labels' for compatibility with the Trainer
tokenized_train = tokenized_train.rename_column("label", "labels")
tokenized_test = tokenized_test.rename_column("label", "labels")

# Convert to PyTorch tensors
tokenized_train.set_format("torch")
tokenized_test.set_format("torch")

"""# 4. Load GPT-2 model（GPT2ForSequenceClassification）"""

# Load GPT-2 for sequence classification
model = GPT2ForSequenceClassification.from_pretrained('gpt2', num_labels=2)

# Set the padding token id to be the same as the tokenizer
model.config.pad_token_id = tokenizer.pad_token_id

# Move model to GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

"""# 5. Fine-tuning: Freeze lower layers of the GPT-2 model to reduce computation"""

# Freeze the first 6 layers of GPT-2 to reduce computation and speed up training
for param in model.transformer.h[:6].parameters():
    param.requires_grad = False

"""# 6. Define evaluation metrics function"""

# Define custom metrics function for evaluation
def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)

    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='binary', zero_division=1)
    acc = accuracy_score(labels, preds)

    return {
        'accuracy': acc,
        'precision': precision,
        'recall': recall,
        'f1': f1
    }

"""# 7. Set training arguments with earlystoppingcallback"""

from transformers import EarlyStoppingCallback

# Set training arguments with Early Stopping and optimizations
training_args = TrainingArguments(
    output_dir='./results',
    eval_strategy="epoch",  # Ensure evaluation happens at each epoch
    logging_strategy="epoch",
    save_strategy="epoch",  # Ensure checkpoints are saved at each epoch
    learning_rate=2e-5,  # Adjust the learning rate
    per_device_train_batch_size=4,  # Lower batch size if needed
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=4,  # Accumulate gradients over 4 steps
    num_train_epochs=10,  # Set higher epochs but Early Stopping will stop earlier if no improvement
    weight_decay=0.01,
    warmup_steps=500,  # Use warmup for learning rate
    fp16=True,  # Enable mixed precision training to speed up the process
    load_best_model_at_end=True,  # Required for EarlyStoppingCallback
    metric_for_best_model="accuracy",  # Metric to use for early stopping
    save_total_limit=2,  # Limit the number of saved checkpoints
)

# Define Early Stopping Callback (Ensure it's imported)
early_stopping = EarlyStoppingCallback(early_stopping_patience=2, early_stopping_threshold=0.001)

"""# 8. Pre-training Evaluation for Comparison"""

# Initialize Trainer with early stopping callback
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_test,
    compute_metrics=compute_metrics,
    callbacks=[early_stopping]  # Add early stopping callback here
)

# Pre-training evaluation (baseline)
predictions_before_training = trainer.predict(tokenized_test)

# Extract true and predicted labels
true_labels_pre = predictions_before_training.label_ids
predicted_labels_pre = predictions_before_training.predictions.argmax(-1)

# Plot confusion matrix for pre-training evaluation
cm_pre = confusion_matrix(true_labels_pre, predicted_labels_pre)
plt.figure(figsize=(5, 5))
sns.heatmap(cm_pre, annot=True, fmt='d', cmap='Blues', cbar=False)
plt.ylabel('Actual Label')
plt.xlabel('Predicted Label')
plt.title('Confusion Matrix (Pre-training)')
plt.show()

# Print baseline results
print("Before training predictions:\n", predictions_before_training.metrics)

"""# 9. Model Training"""

# Initialize Trainer with early stopping callback
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_test,
    compute_metrics=compute_metrics,
    callbacks=[early_stopping]  # Add early stopping callback here
)

# Train the model with Early Stopping enabled
trainer.train()

"""# 10. Model Evaluation"""

# Evaluate the model after training
results = trainer.evaluate()

# Plot confusion matrix for post-training evaluation
cm_post = confusion_matrix(true_labels_pre, predicted_labels_pre)
plt.figure(figsize=(5, 5))
sns.heatmap(cm_post, annot=True, fmt='d', cmap='Blues', cbar=False)
plt.ylabel('Actual Label')
plt.xlabel('Predicted Label')
plt.title('Confusion Matrix (Post-training)')
plt.show()

# Print final evaluation results
print("Evaluation results:\n", results)

"""# 11. Model inference"""

# Perform inference (prediction) on new text inputs
texts = ["I love programming.", "You are so stupid!"]

# Tokenize the input text
inference_encodings = tokenizer(texts, truncation=True, padding=True, return_tensors='pt')

# Ensure the model is in evaluation mode
model.eval()

# Make predictions
with torch.no_grad():
    outputs = model(**inference_encodings)
    logits = outputs.logits
    predictions = torch.argmax(logits, dim=-1)

# Decode the predictions into labels
labels = ['Non-Toxic', 'Toxic']
predicted_labels = [labels[pred] for pred in predictions]

# Display the inference results
for i, text in enumerate(texts):
    print(f"Text: {text}")
    print(f"Predicted Label: {predicted_labels[i]}\n")