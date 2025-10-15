#!/bin/bash

echo "🚀 Installing MCP Servers and Dependencies"
echo "=========================================="

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    
    # Install Node.js using NodeSource repository (more recent version)
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    
    # Verify installation
    if command -v node &> /dev/null; then
        echo "✅ Node.js installed successfully"
        node --version
        npm --version
    else
        echo "❌ Failed to install Node.js"
        exit 1
    fi
else
    echo "✅ Node.js already installed"
    node --version
    npm --version
fi

echo ""
echo "📦 Installing MCP Server packages..."

# Install MCP server packages globally
echo "Installing filesystem server..."
sudo npm install -g @modelcontextprotocol/server-filesystem

echo "Installing brave-search server..."
sudo npm install -g @modelcontextprotocol/server-brave-search

echo "Installing postgres server..."
sudo npm install -g @modelcontextprotocol/server-postgres

echo ""
echo "🔧 Verifying installations..."

# Test if packages are installed
if npx @modelcontextprotocol/server-filesystem --help &> /dev/null; then
    echo "✅ Filesystem server installed"
else
    echo "❌ Filesystem server installation failed"
fi

if npx @modelcontextprotocol/server-brave-search --help &> /dev/null; then
    echo "✅ Brave-search server installed"
else
    echo "❌ Brave-search server installation failed"
fi

if npx @modelcontextprotocol/server-postgres --help &> /dev/null; then
    echo "✅ Postgres server installed"
else
    echo "❌ Postgres server installation failed"
fi

echo ""
echo "🎉 MCP Server installation complete!"
echo ""
echo "📝 Next steps:"
echo "1. Set up your API keys in .env file:"
echo "   - BRAVE_API_KEY=your_brave_api_key"
echo "   - POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/dbname"
echo ""
echo "2. Test the connection:"
echo "   python3 chain_chat_main.py 'list files in current directory'"
echo ""
