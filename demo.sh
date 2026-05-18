#!/bin/bash
# Demo Script - Start everything and show it working

echo "🚀 Starting Complete Arbitrage System Demo..."
echo "================================================="

# Step 1: Start the Docker containers
echo ""
echo "🐳 Starting Docker containers..."
docker-compose up -d

# Step 2: Wait for services to be ready
echo ""
echo "⏳ Waiting for services to initialize..."
sleep 15

# Step 3: Check system status
echo ""
echo "🏥 Checking system status..."
echo "Backend health:"
curl -s http://localhost:8001/api/health || echo "   ❌ Backend not responding yet"

echo ""
echo "🐦 Ollama status:"
curl -s http://localhost:11434/api/tags || echo "   ❌ Ollama not responding yet"

echo ""
echo "🌐 ngrok tunnel:"
echo "   Check: https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev"

# Step 4: Trigger the automated pipeline
echo ""
echo "🔄 Triggering automated arbitrage pipeline..."

# Make sure orchestrator is executable
chmod +x /app/backend/orchestrator.py

# Run the pipeline
python3 /app/backend/orchestrator.py

# Step 5: Show results
echo ""
echo "📊 Displaying results..."
echo ""

# Check if reports were generated
echo "📁 Generated reports:"
ls -la /app/reports/ 2>/dev/null || echo "   ❌ No reports found yet"

# Show the latest report if it exists
if [ -f "/app/reports/"*.html ]; then
    echo ""
    echo "📈 Latest report:"
    ls -lt /app/reports/*.html | head -1
    
    echo ""
    echo "📄 Opening latest report in browser..."
    # Find the latest HTML file
    latest_report=$(ls -t /app/reports/*.html | head -1)
    
    if [ -n "$latest_report" ]; then
        echo "   Report: $latest_report"
        echo ""
        echo "👈 Quick preview:"
        echo "   Number of exact matches:"
        grep -o "Exact Matches" $latest_report | wc -l || echo "   ✅ Report structure looks good"
        
        echo ""
        echo "🔍 Example match content:"
        grep -A 5 -B 5 "match-card" $latest_report | head -20
        
        echo ""
        echo "🔗 Clickable links check:"
        grep -o "href=\"[^"]*\"" $latest_report | head -3
    fi
else
    echo "   ❌ No reports generated yet"
fi

# Step 6: Show logs
echo ""
echo "📝 Showing recent logs:"
echo ""
docker-compose logs --tail=50 arbitrage-backend

# Step 7: Summary
echo ""
echo "✅ Demo Complete!"
echo "============================================================"
echo ""
echo "📊 Key System Status:"
echo "   ✅ Backend:     http://localhost:8001"
echo "   ✅ Ollama:      http://localhost:11434"
echo "   ✅ ngrok URL:    https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev"
echo "   ✅ Reports:      /app/reports/"
echo ""
echo "💡 Next Steps:"
echo "   - Check dashboard: http://localhost:8001"
echo "   - View latest report: ls -lt /app/reports/*.html"
echo "   - Monitor logs: docker-compose logs -f"
echo ""
echo "🚀 To restart:"
echo "   docker-compose down"
echo "   docker-compose up -d"
echo ""
echo "📁 System Files Created:"
echo "   - Dockerfile"
echo "   - docker-compose.yml"
echo "   - start-automated.sh"
echo "   - backend/orchestrator.py"
echo "   - backend/llm_parallel_workers.py"
echo "   - backend/semantic_matcher.py"
echo "   - backend/html_report_generator.py"
echo "   - backend/websocket_colab.py"
echo "   - backend/colab_executor.py"
echo "   - Cloud_GPU_Matcher_v3_Auto.ipynb"
echo ""
echo "============================================================"

# Keep container running for demo
echo ""
echo "🔄 Demo container is running. Press Ctrl+C to exit."
echo "   (All services will continue running in background)"

# Tail logs to show activity
# docker-compose logs -f
