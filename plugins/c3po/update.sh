#!/bin/bash

# C-3PO Plugin Update Script
# This script updates the Ollama model and checks for plugin updates

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
        systemctl is-active --quiet "ollama" 2>/dev/null
    fi
}

# Function to update model
update_model() {
    local model_name="$1"
    
    print_status "Updating model: $model_name"
    
    if ! is_ollama_running; then
        print_error "Ollama is not running. Please start Ollama first."
        exit 1
    fi
    
    # Pull the latest version
    ollama pull "$model_name"
    
    print_success "Model $model_name updated successfully"
}

# Function to list available models
list_models() {
    print_status "Installed models:"
    ollama list
}

# Function to show model information
show_model_info() {
    local model_name="$1"
    
    print_status "Model information for: $model_name"
    ollama show "$model_name"
}

# Function to test model
test_model() {
    local model_name="$1"
    
    print_status "Testing model: $model_name"
    
    local test_response
    test_response=$(ollama run "$model_name" "Say 'C-3PO systems updated!' in a polite, formal manner." 2>/dev/null)
    
    if [ -n "$test_response" ]; then
        print_success "Model test successful:"
        echo "$test_response"
    else
        print_warning "Model test failed"
    fi
}

# Function to check for Ollama updates
update_ollama() {
    print_status "Checking for Ollama updates..."
    
    if command_exists curl; then
        curl -fsSL https://ollama.com/install.sh | sh
        print_success "Ollama updated successfully"
    else
        print_warning "curl not found. Please update Ollama manually."
    fi
}

# Function to show help
show_help() {
    echo "C-3PO Plugin Update Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --model MODEL     Update specific model (default: $DEFAULT_MODEL)"
    echo "  --all-models      Update all installed models"
    echo "  --list            List all installed models"
    echo "  --test MODEL      Test a specific model"
    echo "  --info MODEL      Show information about a model"
    echo "  --update-ollama   Update Ollama itself"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Update default model"
    echo "  $0 --model llama3.2:7b      # Update specific model"
    echo "  $0 --all-models              # Update all models"
    echo "  $0 --test llama3.2:3b        # Test a model"
}

# Main function
main() {
    echo ""
    echo "🤖 C-3PO Plugin Updater 🤖"
    echo "============================"
    echo ""
    
    # Default action
    local action="update_default"
    local model="$DEFAULT_MODEL"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --model)
                model="$2"
                action="update_model"
                shift 2
                ;;
            --all-models)
                action="update_all"
                shift
                ;;
            --list)
                action="list"
                shift
                ;;
            --test)
                model="$2"
                action="test"
                shift 2
                ;;
            --info)
                model="$2"
                action="info"
                shift 2
                ;;
            --update-ollama)
                action="update_ollama"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check if Ollama is available
    if ! command_exists ollama; then
        print_error "Ollama is not installed. Please run install.sh first."
        exit 1
    fi
    
    # Execute the requested action
    case $action in
        update_default|update_model)
            update_model "$model"
            test_model "$model"
            ;;
        update_all)
            print_status "Updating all installed models..."
            ollama list | tail -n +2 | awk '{print $1}' | while read -r model_name; do
                if [ -n "$model_name" ] && [ "$model_name" != "NAME" ]; then
                    update_model "$model_name"
                fi
            done
            ;;
        list)
            list_models
            ;;
        test)
            test_model "$model"
            ;;
        info)
            show_model_info "$model"
            ;;
        update_ollama)
            update_ollama
            ;;
    esac
    
    print_success "Update complete!"
}

# Run main function
main "$@"
