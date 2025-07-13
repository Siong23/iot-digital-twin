# Step 1: Train with default parameters
# Create dataloaders with default batch size
batch_size = 32
train_loader, val_loader, test_loader = create_data_loaders(batch_size)

# Define and train TSMixer with default parameters
default_model = TSMixer(
    seq_len=X_train_seq.shape[1],          
    feat_dim=X_train_seq.shape[2],         
    num_classes=len(np.unique(y_train_seq)), 
    hidden_dim=64,
    num_blocks=15,
    dropout=0.1,
    use_channel_attention=False,
    use_temporal_attention=False,
    attention_reduction=16
).to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(default_model.parameters(), lr=0.001)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)

# Call train_model with parameters in the correct order
default_model, base_history = train_model(
    model=default_model,
    train_loader=train_loader,
    val_loader=val_loader,
    criterion=criterion,
    optimizer=optimizer,
    scheduler=scheduler,
    num_epochs=30,
    patience=5
)

# Evaluate base model
def calculate_accuracy(model, data_loader):
    model.eval()
    correct = 0
    total = 0
    
    with torch.no_grad():
        for inputs, labels in data_loader:
            outputs = model(inputs)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    
    return correct / total

# Then use this instead of the second evaluate_model function
base_val_acc = calculate_accuracy(default_model, val_loader)
print(f"Base TSMixer validation accuracy: {base_val_acc:.4f}")