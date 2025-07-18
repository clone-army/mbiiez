#!/bin/bash

# C-3PO Plugin Installation Script
# This script installs Ollama and sets up the LLM model for the C-3PO plugin

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_MODEL="llama3.2:3b"
OLLAMA_URL="http://localhost:11434"
OLLAMA_SERVICE_NAME="ollama"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Ollama is running
is_ollama_running() {
    if command_exists curl; then
        curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1
    else
        systemctl is-active --quiet "$OLLAMA_SERVICE_NAME" 2>/dev/null
    fi
}

# Function to wait for Ollama to be ready
wait_for_ollama() {
    print_status "Waiting for Ollama to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if is_ollama_running; then
            print_success "Ollama is ready!"
            return 0
        fi
        
        sleep 2
        attempt=$((attempt + 1))
        echo -n "."
    done
    
    print_error "Ollama did not start within expected time"
    return 1
}

# Function to install Ollama
install_ollama() {
    print_status "Installing Ollama..."
    
    if command_exists ollama; then
        print_success "Ollama is already installed"
        return 0
    fi
    
    # Download and install Ollama
    if command_exists curl; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        print_error "curl is required to install Ollama"
        exit 1
    fi
    
    if command_exists ollama; then
        print_success "Ollama installed successfully"
    else
        print_error "Failed to install Ollama"
        exit 1
    fi
}

# Function to start Ollama service
start_ollama() {
    print_status "Starting Ollama service..."
    
    if is_ollama_running; then
        print_success "Ollama is already running"
        return 0
    fi
    
    # Try to start as systemd service first
    if command_exists systemctl; then
        if systemctl list-unit-files | grep -q "ollama.service"; then
            sudo systemctl start ollama
            sudo systemctl enable ollama
            print_success "Ollama service started"
            return 0
        fi
    fi
    
    # If no systemd service, try to start in background
    if command_exists ollama; then
        print_status "Starting Ollama in background..."
        nohup ollama serve > /dev/null 2>&1 &
        sleep 5
        
        if is_ollama_running; then
            print_success "Ollama started in background"
        else
            print_error "Failed to start Ollama"
            exit 1
        fi
    else
        print_error "Ollama command not found"
        exit 1
    fi
}

# Function to check if model exists
model_exists() {
    local model_name="$1"
    ollama list | grep -q "^$model_name"
}

# Function to install/update model
install_model() {
    local model_name="$1"
    
    print_status "Checking model: $model_name"
    
    if model_exists "$model_name"; then
        print_status "Model $model_name already exists. Checking for updates..."
        ollama pull "$model_name"
        print_success "Model $model_name updated successfully"
    else
        print_status "Installing model: $model_name"
        print_warning "This may take several minutes depending on your internet connection..."
        
        ollama pull "$model_name"
        
        if model_exists "$model_name"; then
            print_success "Model $model_name installed successfully"
        else
            print_error "Failed to install model $model_name"
            exit 1
        fi
    fi
}

# Function to test the model
test_model() {
    local model_name="$1"
    
    print_status "Testing model: $model_name"
    
    local test_response
    test_response=$(ollama run "$model_name" "Say 'C-3PO is ready!' in a formal, polite manner." 2>/dev/null | head -1)
    
    if [ -n "$test_response" ]; then
        print_success "Model test successful: $test_response"
    else
        print_warning "Model test failed, but model appears to be installed"
    fi
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # First try system package manager
    if command_exists apt-get; then
        if sudo apt-get update && sudo apt-get install -y python3-requests; then
            print_success "Python dependencies installed via apt"
            return 0
        fi
    elif command_exists yum; then
        if sudo yum install -y python3-requests; then
            print_success "Python dependencies installed via yum"
            return 0
        fi
    elif command_exists dnf; then
        if sudo dnf install -y python3-requests; then
            print_success "Python dependencies installed via dnf"
            return 0
        fi
    fi
    
    # If system package manager fails, try pip with --break-system-packages
    if command_exists pip3; then
        if pip3 install requests --break-system-packages; then
            print_success "Python dependencies installed via pip3"
            return 0
        fi
    elif command_exists pip; then
        if pip install requests --break-system-packages; then
            print_success "Python dependencies installed via pip"
            return 0
        fi
    fi
    
    print_warning "Could not install Python dependencies automatically."
    print_warning "Please install 'requests' manually using one of:"
    print_warning "  sudo apt install python3-requests"
    print_warning "  pip3 install requests --break-system-packages"
    print_warning "  Or create a virtual environment"
}

# Function to display system requirements
check_system_requirements() {
    print_status "Checking system requirements..."
    
    # Check available memory
    local mem_total
    mem_total=$(free -m | awk 'NR==2{print $2}')
    
    if [ "$mem_total" -lt 2048 ]; then
        print_warning "Low memory detected (${mem_total}MB). Consider using llama3.2:1b model for better performance."
        echo "You can change the model in your config to: llama3.2:1b"
    elif [ "$mem_total" -lt 4096 ]; then
        print_status "Memory: ${mem_total}MB - Good for llama3.2:3b model"
    else
        print_success "Memory: ${mem_total}MB - Excellent for larger models"
    fi
    
    # Check disk space
    local disk_space
    disk_space=$(df -h / | awk 'NR==2{print $4}')
    print_status "Available disk space: $disk_space"
}

# Function to create example configuration
create_example_config() {
    local config_file="c3po_config_example.json"
    
    print_status "Creating example configuration..."
    
    cat > "$config_file" << EOF
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://localhost:11434",
            "model": "$DEFAULT_MODEL",
            "max_tokens": 100,
            "temperature": 0.7,
            "chat_commands": ["!c3po", "!3po", "!droid", "!protocol"],
            "personality": "You are C-3PO, a protocol droid fluent in over six million forms of communication. You are proper, polite, sometimes anxious, and knowledgeable about Star Wars lore. You often worry about the odds and express concerns about dangerous situations. Keep responses brief and in character. Always speak in a polite, formal manner and occasionally mention odds or express worry about dangerous situations.",
            "auto_responses": {
                "enabled": true,
                "kill_announcements": true,
                "welcome_messages": true,
                "map_comments": true
            }
        }
    }
}
EOF
    
    print_success "Example configuration created: $config_file"
}

# Function to show post-installation instructions
show_instructions() {
    echo ""
    echo "============================================="
    echo "🤖 C-3PO Plugin Installation Complete! 🤖"
    echo "============================================="
    echo ""
    echo "Next steps:"
    echo "1. Add the C-3PO plugin configuration to your instance config file"
    echo "2. Copy the settings from: c3po_config_example.json"
    echo "3. Restart your MBIIEZ instance"
    echo ""
    echo "Test the installation:"
    echo "  ollama run $DEFAULT_MODEL \"Hello, I am C-3PO!\""
    echo ""
    echo "Players can chat with C-3PO using:"
    echo "  !c3po <message>"
    echo "  !3po <message>"
    echo "  !droid <message>"
    echo "  !protocol <message>"
    echo ""
    echo "Enjoy your new protocol droid companion!"
    echo "============================================="
}

# Main installation function
main() {
    echo ""
    echo "🤖 C-3PO Plugin Installer 🤖"
    echo "=============================="
    echo ""
    
    # Parse command line arguments
    MODEL="$DEFAULT_MODEL"
    while [[ $# -gt 0 ]]; do
        case $1 in
            --model)
                MODEL="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [--model MODEL_NAME]"
                echo ""
                echo "Options:"
                echo "  --model    Specify the model to install (default: $DEFAULT_MODEL)"
                echo ""
                echo "Available models:"
                echo "  llama3.2:1b  - Lightweight, fast (1GB RAM)"
                echo "  llama3.2:3b  - Balanced, good quality (3GB RAM)"
                echo "  llama3.2:7b  - High quality, slower (7GB RAM)"
                echo "  llama3.1:8b  - Excellent quality, slower (8GB RAM)"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_status "Installing C-3PO plugin with model: $MODEL"
    
    # Check system requirements
    check_system_requirements
    
    # Install components
    install_ollama
    install_python_deps
    start_ollama
    wait_for_ollama
    install_model "$MODEL"
    test_model "$MODEL"
    create_example_config
    
    # Show completion message
    show_instructions
}

# Run main function
main "$@"
