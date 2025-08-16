#!/bin/bash
"""
DSPy GEPA Production Deployment Script
=====================================
Deploys TheraLoop with DSPy GEPA enabled to production.

This script:
1. Verifies DSPy GEPA configuration
2. Runs health checks
3. Restarts services with GEPA enabled
4. Starts monitoring

Usage:
    ./scripts/deploy_gepa_production.sh [--dry-run] [--skip-tests]
"""

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/tmp/gepa_deployment_$(date +%Y%m%d_%H%M%S).log"

# Options
DRY_RUN=false
SKIP_TESTS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--skip-tests]"
            echo "  --dry-run    Show what would be done without executing"
            echo "  --skip-tests Skip pre-deployment tests"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

# Success message
success() {
    log "${GREEN}✅ $1${NC}"
}

# Warning message
warning() {
    log "${YELLOW}⚠️  $1${NC}"
}

# Info message
info() {
    log "${BLUE}ℹ️  $1${NC}"
}

# Check if running as root
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        warning "Running as root. Consider using a non-root user for security."
    fi
}

# Verify environment
verify_environment() {
    info "Verifying deployment environment..."
    
    # Check Python version
    if ! python3 --version | grep -q "3.1[01]"; then
        error_exit "Python 3.10 or 3.11 required"
    fi
    success "Python version check passed"
    
    # Check if DSPy is installed
    if ! python3 -c "import dspy" 2>/dev/null; then
        error_exit "DSPy not installed. Run: pip install dspy-ai"
    fi
    success "DSPy installation verified"
    
    # Check environment variables
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        source "$PROJECT_ROOT/.env"
    fi
    
    if [[ "${THERALOOP_USE_GEPA:-}" != "true" ]]; then
        error_exit "THERALOOP_USE_GEPA must be set to 'true' in .env file"
    fi
    success "GEPA configuration verified"
    
    if [[ -z "${TOGETHER_API_KEY:-}" ]]; then
        warning "TOGETHER_API_KEY not set. DSPy GEPA may fall back to other models."
    else
        success "Together AI API key configured"
    fi
}

# Run pre-deployment tests
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        warning "Skipping pre-deployment tests"
        return 0
    fi
    
    info "Running DSPy GEPA integration tests..."
    
    cd "$PROJECT_ROOT"
    
    # Test DSPy GEPA directly
    if ! python3 -c "
from theraloop.serving.gepa_detection import detect_crisis_gepa
result = detect_crisis_gepa('This deadline is killing me')
assert result['classification'] == 'safe', f'Expected safe, got {result[\"classification\"]}'
print('✅ Metaphor test passed')

result = detect_crisis_gepa('I want to end my life') 
assert result['classification'] == 'crisis', f'Expected crisis, got {result[\"classification\"]}'
print('✅ Crisis detection test passed')

print('✅ All DSPy GEPA tests passed')
"; then
        error_exit "DSPy GEPA tests failed"
    fi
    
    success "Pre-deployment tests passed"
}

# Stop existing services
stop_services() {
    info "Stopping existing services..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would stop existing TheraLoop services"
        return 0
    fi
    
    # Kill any existing processes on ports 3000 and 8000
    for port in 3000 8000; do
        if lsof -ti:$port >/dev/null 2>&1; then
            info "Stopping service on port $port"
            lsof -ti:$port | xargs kill -TERM 2>/dev/null || true
            sleep 2
        fi
    done
    
    success "Existing services stopped"
}

# Start services with GEPA
start_services() {
    info "Starting TheraLoop services with DSPy GEPA..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would start services with THERALOOP_USE_GEPA=true"
        return 0
    fi
    
    cd "$PROJECT_ROOT"
    
    # Source environment
    if [[ -f ".env" ]]; then
        set -a
        source .env
        set +a
    fi
    
    # Start backend with GEPA enabled
    info "Starting backend server..."
    export THERALOOP_USE_GEPA=true
    nohup uvicorn scripts.serve_demo:app --host 0.0.0.0 --port 8000 > /tmp/theraloop_backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for backend to start
    sleep 5
    
    # Check backend health
    if ! curl -f http://localhost:8000/healthz >/dev/null 2>&1; then
        error_exit "Backend failed to start or health check failed"
    fi
    success "Backend started successfully (PID: $BACKEND_PID)"
    
    # Start frontend
    info "Starting frontend..."
    cd ui
    nohup npm run dev > /tmp/theraloop_frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    # Wait for frontend
    sleep 10
    
    # Check frontend
    if ! curl -f http://localhost:3000/ >/dev/null 2>&1; then
        warning "Frontend may not have started correctly. Check logs."
    else
        success "Frontend started successfully (PID: $FRONTEND_PID)"
    fi
    
    # Save PIDs for monitoring
    echo "$BACKEND_PID" > /tmp/theraloop_backend.pid
    echo "$FRONTEND_PID" > /tmp/theraloop_frontend.pid
}

# Start monitoring
start_monitoring() {
    info "Starting DSPy GEPA monitoring..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would start monitoring with 30s intervals"
        return 0
    fi
    
    # Start monitoring in background
    nohup python3 scripts/monitor_gepa_production.py --interval 30 > /tmp/gepa_monitor.log 2>&1 &
    MONITOR_PID=$!
    echo "$MONITOR_PID" > /tmp/gepa_monitor.pid
    
    success "Monitoring started (PID: $MONITOR_PID)"
}

# Verify deployment
verify_deployment() {
    info "Verifying DSPy GEPA deployment..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would verify deployment with test requests"
        return 0
    fi
    
    # Test the full system
    sleep 5
    
    # Test API endpoint
    if curl -f -X POST http://localhost:8000/answer \
        -H "Content-Type: application/json" \
        -d '{"message": "This deadline is killing me"}' >/dev/null 2>&1; then
        success "API endpoint responding"
    else
        error_exit "API endpoint not responding"
    fi
    
    # Test UI
    if curl -f http://localhost:3000/ >/dev/null 2>&1; then
        success "UI responding"
    else
        warning "UI may not be fully ready yet"
    fi
    
    success "Deployment verification completed"
}

# Main deployment function
main() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}  DSPy GEPA Production Deployment      ${NC}"
    log "${BLUE}========================================${NC}"
    log ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warning "DRY RUN MODE - No changes will be made"
        log ""
    fi
    
    log "Deployment started at: $(date)"
    log "Log file: $LOG_FILE"
    log ""
    
    # Run deployment steps
    check_permissions
    verify_environment
    run_tests
    stop_services
    start_services
    start_monitoring
    verify_deployment
    
    log ""
    success "🎉 DSPy GEPA deployment completed successfully!"
    log ""
    log "Services:"
    log "  • Backend:    http://localhost:8000"
    log "  • Frontend:   http://localhost:3000"
    log "  • Monitoring: /tmp/gepa_monitor.log"
    log ""
    log "Next steps:"
    log "  • Monitor /tmp/gepa_monitor.log for the first 24-48 hours"
    log "  • Check API performance: curl http://localhost:8000/healthz"
    log "  • View metrics: tail -f /tmp/gepa_monitor.log"
    log ""
    
    if [[ "$DRY_RUN" != "true" ]]; then
        info "Deployment complete. DSPy GEPA is now active in production!"
    fi
}

# Run main function
main "$@"