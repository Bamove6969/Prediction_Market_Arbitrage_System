"""
Interactive HTML Report Generator
Creates visually pleasing reports with Plotly.js, collapsible sections, and clickable links
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


def generate_html_report(matches: List[Dict[str, Any]], output_path: str = None) -> str:
    """
    Generate an interactive HTML report with:
    - Collapsible sections for each match
    - Exact question text as displayed on each site
    - Two blue clickable links to the original questions
    - Plotly.js visualizations
    - Modern, clean styling
    """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arbitrage Match Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    
    <!-- Tailwind CSS for styling -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- Alpine.js for interactivity -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.3/dist/cdn.min.js"></script>
    
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        body {{
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .match-card {{
            transition: all 0.3s ease;
        }}
        
        .match-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
        }}
        
        .site-link {{
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }}
        
        .site-link:hover {{
            color: #1d4ed8;
            text-decoration: underline;
        }}
        
        .site-link::after {{
            content: '↗';
            font-size: 0.8em;
        }}
        
        .collapsible-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}
        
        .collapsible-content.open {{
            max-height: 2000px;
        }}
        
        .roi-badge {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }}
        
        .verified-badge {{
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        }}
        
        .platform-tag {{
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
        }}
    </style>
</head>
<body class="p-8">
    <div class="max-w-7xl mx-auto" x-data="reportApp()">
        <!-- Header -->
        <div class="bg-white rounded-2xl shadow-2xl p-8 mb-8">
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h1 class="text-4xl font-bold text-gray-900 mb-2">
                        🔍 Arbitrage Match Report
                    </h1>
                    <p class="text-gray-600">
                        Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
                <div class="text-right">
                    <div class="text-5xl font-bold text-blue-600">{len(matches)}</div>
                    <div class="text-gray-500">Exact Matches</div>
                </div>
            </div>
            
            <!-- Stats Overview -->
            <div class="grid grid-cols-4 gap-4 mt-6">
                <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4">
                    <div class="text-2xl font-bold text-blue-600" x-text="stats.avgROI"></div>
                    <div class="text-sm text-blue-700">Avg ROI</div>
                </div>
                <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4">
                    <div class="text-2xl font-bold text-green-600" x-text="stats.highestROI"></div>
                    <div class="text-sm text-green-700">Highest ROI</div>
                </div>
                <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4">
                    <div class="text-2xl font-bold text-purple-600" x-text="stats.verifiedCount"></div>
                    <div class="text-sm text-purple-700">LLM Verified</div>
                </div>
                <div class="bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl p-4">
                    <div class="text-2xl font-bold text-orange-600" x-text="stats.platformsCount"></div>
                    <div class="text-sm text-orange-700">Platforms</div>
                </div>
            </div>
            
            <!-- ROI Distribution Chart -->
            <div class="mt-6">
                <div id="roi-chart" class="w-full h-64"></div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="bg-white rounded-xl shadow-lg p-4 mb-6">
            <div class="flex gap-4 items-center">
                <input 
                    type="text" 
                    x-model="searchQuery"
                    placeholder="🔎 Search questions..."
                    class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                <input 
                    type="number" 
                    x-model.number="minROI"
                    placeholder="Min ROI %"
                    class="w-32 px-4 py-2 border border-gray-300 rounded-lg"
                >
                <select x-model="platformFilter" class="px-4 py-2 border border-gray-300 rounded-lg">
                    <option value="">All Platforms</option>
                    <template x-for="platform in platforms" :key="platform">
                        <option :value="platform" x-text="platform"></option>
                    </template>
                </select>
                <button 
                    @click="expandAll = !expandAll"
                    class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                    <span x-text="expandAll ? 'Collapse All' : 'Expand All'"></span>
                </button>
            </div>
        </div>
        
        <!-- Match Cards -->
        <div class="space-y-4">
            <template x-for="(match, index) in filteredMatches" :key="index">
                <div class="match-card bg-white rounded-xl shadow-lg overflow-hidden">
                    <!-- Card Header (Always Visible) -->
                    <div class="p-6 bg-gradient-to-r from-gray-50 to-white">
                        <div class="flex items-start justify-between">
                            <div class="flex-1">
                                <div class="flex items-center gap-3 mb-3">
                                    <span class="roi-badge text-white px-3 py-1 rounded-full text-sm font-semibold">
                                        <span x-text="match.original_roi.toFixed(2) + '% ROI'"></span>
                                    </span>
                                    <template x-if="match.isMatch">
                                        <span class="verified-badge text-white px-3 py-1 rounded-full text-sm font-semibold">
                                            ✓ LLM Verified
                                        </span>
                                    </template>
                                </div>
                                
                                <!-- Site A -->
                                <div class="mb-4">
                                    <div class="flex items-center gap-2 mb-2">
                                        <span class="platform-tag px-2 py-1 rounded text-xs font-medium" x-text="match.marketA.platform"></span>
                                        <a :href="match.marketA.url" target="_blank" class="site-link">
                                            View on {match.marketA.platform || 'Site'}
                                        </a>
                                    </div>
                                    <p class="text-gray-800 font-medium" x-text="match.marketA.title"></p>
                                    <p class="text-sm text-gray-600 mt-1">
                                        Yes Price: <span class="font-semibold" x-text="(match.marketA.yesPrice * 100).toFixed(2) + '%'"></span>
                                    </p>
                                </div>
                                
                                <!-- Site B -->
                                <div>
                                    <div class="flex items-center gap-2 mb-2">
                                        <span class="platform-tag px-2 py-1 rounded text-xs font-medium" x-text="match.marketB.platform"></span>
                                        <a :href="match.marketB.url" target="_blank" class="site-link">
                                            View on {match.marketB.platform || 'Site'}
                                        </a>
                                    </div>
                                    <p class="text-gray-800 font-medium" x-text="match.marketB.title"></p>
                                    <p class="text-sm text-gray-600 mt-1">
                                        Yes Price: <span class="font-semibold" x-text="(match.marketB.yesPrice * 100).toFixed(2) + '%'"></span>
                                    </p>
                                </div>
                            </div>
                            
                            <button 
                                @click="toggleExpand(index)"
                                class="ml-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                            >
                                <span x-text="match.expanded ? '▼' : '▶'"></span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Collapsible Details -->
                    <div class="collapsible-content" :class="{{ 'open': match.expanded }}">
                        <div class="p-6 bg-gray-50 border-t">
                            <div class="grid grid-cols-2 gap-6">
                                <!-- LLM Analysis -->
                                <div>
                                    <h4 class="font-semibold text-gray-700 mb-2">🤖 LLM Analysis</h4>
                                    <p class="text-sm text-gray-600" x-text="match.explanation || match.semantic_analysis?.differences?.join(', ') || 'Questions are semantically identical'"></p>
                                </div>
                                
                                <!-- Match Details -->
                                <div>
                                    <h4 class="font-semibold text-gray-700 mb-2">📊 Match Details</h4>
                                    <div class="text-sm text-gray-600 space-y-1">
                                        <div>Model: <span class="font-medium" x-text="match.model || 'N/A'"></span></div>
                                        <div>Match Score: <span class="font-medium" x-text="(match.match_score || match.semantic_analysis?.similarity_score || 0).toFixed(2)"></span></div>
                                        <div>Worker: <span class="font-medium" x-text="match.worker || 'N/A'"></span></div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Arbitrage Calculation -->
                            <div class="mt-4 p-4 bg-white rounded-lg">
                                <h4 class="font-semibold text-gray-700 mb-2">💰 Arbitrage Calculation</h4>
                                <div class="grid grid-cols-3 gap-4 text-sm">
                                    <div>
                                        <div class="text-gray-600">Combined Cost</div>
                                        <div class="font-semibold text-gray-900" x-text="calculateCost(match)"></div>
                                    </div>
                                    <div>
                                        <div class="text-gray-600">Guaranteed Return</div>
                                        <div class="font-semibold text-green-600">$1.00</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-600">Profit Margin</div>
                                        <div class="font-semibold text-green-600" x-text="match.original_roi.toFixed(2) + '%'"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </template>
        </div>
        
        <!-- Empty State -->
        <div x-show="filteredMatches.length === 0" class="text-center py-12">
            <div class="text-6xl mb-4">🔍</div>
            <h3 class="text-xl font-semibold text-white mb-2">No matches found</h3>
            <p class="text-white/80">Try adjusting your filters</p>
        </div>
    </div>
    
    <script>
        function reportApp() {{
            return {{
                matches: {json.dumps(matches[:100])},  // Limit initial load
                searchQuery: '',
                minROI: 0,
                platformFilter: '',
                expandAll: false,
                platforms: {json.dumps(list(set([m['marketA']['platform'] for m in matches] + [m['marketB']['platform'] for m in matches])))},
                
                get stats() {{
                    const rois = this.matches.map(m => m.original_roi);
                    return {{
                        avgROI: (rois.reduce((a, b) => a + b, 0) / rois.length).toFixed(2) + '%',
                        highestROI: Math.max(...rois).toFixed(2) + '%',
                        verifiedCount: this.matches.filter(m => m.isMatch).length,
                        platformsCount: this.platforms.length
                    }};
                }},
                
                get filteredMatches() {{
                    return this.matches.filter(match => {{
                        const matchesSearch = this.searchQuery === '' || 
                            match.marketA.title.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
                            match.marketB.title.toLowerCase().includes(this.searchQuery.toLowerCase());
                        
                        const matchesROI = match.original_roi >= this.minROI;
                        
                        const matchesPlatform = this.platformFilter === '' ||
                            match.marketA.platform === this.platformFilter ||
                            match.marketB.platform === this.platformFilter;
                        
                        return matchesSearch && matchesROI && matchesPlatform;
                    }});
                }},
                
                toggleExpand(index) {{
                    this.matches[index].expanded = !this.matches[index].expanded;
                }},
                
                calculateCost(match) {{
                    const cost = match.marketA.yesPrice + (1 - match.marketB.yesPrice);
                    return '$' + cost.toFixed(4);
                }},
                
                init() {{
                    // Initialize Plotly chart
                    const rois = this.matches.map(m => m.original_roi);
                    const trace = {{
                        x: rois,
                        type: 'histogram',
                        marker: {{
                            color: '#3b82f6',
                            opacity: 0.7
                        }},
                        nbinsx: 30
                    }};
                    
                    const layout = {{
                        title: 'ROI Distribution',
                        xaxis: {{ title: 'ROI (%)' }},
                        yaxis: {{ title: 'Count' }},
                        margin: {{ t: 40, b: 40, l: 40, r: 40 }},
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)'
                    }};
                    
                    Plotly.newPlot('roi-chart', [trace], layout, {{displayModeBar: false}});
                }}
            }}
        }}
    </script>
</body>
</html>"""
    
    # Save to file if path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"HTML report saved to: {output_path}")
    
    return html


if __name__ == "__main__":
    # Test with sample data
    test_matches = [
        {
            "marketA": {
                "title": "Will Bitcoin reach $100,000 by December 2025?",
                "platform": "Polymarket",
                "yesPrice": 0.42,
                "url": "https://polymarket.com/event/bitcoin-100k"
            },
            "marketB": {
                "title": "Bitcoin to hit $100K before 2026",
                "platform": "PredictIt",
                "yesPrice": 0.38,
                "url": "https://predictit.org/market/btc-100k"
            },
            "original_roi": 21.05,
            "isMatch": True,
            "match_score": 0.95,
            "explanation": "Both questions ask about Bitcoin reaching $100,000 before 2026",
            "expanded": False
        }
    ]
    
    html = generate_html_report(test_matches, "/tmp/test_report.html")
    print(f"Generated report with {len(test_matches)} matches")
