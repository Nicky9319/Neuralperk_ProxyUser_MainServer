#!/bin/bash

echo "=== Vast.ai SSH Connection Helper ==="
echo ""

INSTANCE_ID="25681251"

echo "🔍 Checking instance status..."
vastai show instance $INSTANCE_ID

echo ""
echo "🔗 Getting SSH connection details..."
SSH_URL=$(vastai ssh-url $INSTANCE_ID)
echo "SSH URL: $SSH_URL"

# Extract host and port from SSH URL
SSH_HOST=$(echo $SSH_URL | sed 's/ssh:\/\/root@//' | sed 's/:.*//')
SSH_PORT=$(echo $SSH_URL | sed 's/.*://')

echo "SSH Host: $SSH_HOST"
echo "SSH Port: $SSH_PORT"

echo ""
echo "📋 SSH Connection Commands:"
echo "1. Basic SSH:"
echo "   ssh -p $SSH_PORT root@$SSH_HOST"
echo ""
echo "2. SSH with verbose output (for debugging):"
echo "   ssh -v -p $SSH_PORT root@$SSH_HOST"
echo ""
echo "3. SSH with connection timeout:"
echo "   ssh -o ConnectTimeout=10 -p $SSH_PORT root@$SSH_HOST"
echo ""

echo "🔄 Testing SSH connection..."
echo "Attempting to connect..."

# Test SSH connection with timeout
timeout 10 ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p $SSH_PORT root@$SSH_HOST "echo 'SSH connection successful!'; uname -a; python3 --version" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ SSH connection successful!"
    echo ""
    echo "🚀 You can now connect manually using:"
    echo "ssh -p $SSH_PORT root@$SSH_HOST"
else
    echo "❌ SSH connection failed or timed out"
    echo ""
    echo "💡 Possible reasons:"
    echo "   - Instance is still starting up (wait 1-2 minutes)"
    echo "   - SSH daemon not running in the container"
    echo "   - Network connectivity issues"
    echo ""
    echo "🔄 You can try again in a few minutes with:"
    echo "ssh -p $SSH_PORT root@$SSH_HOST"
fi

echo ""
echo "📝 To check instance logs:"
echo "vastai logs $INSTANCE_ID --tail 20"
echo ""
echo "🗑️  To destroy instance when done:"
echo "vastai destroy instance $INSTANCE_ID"
