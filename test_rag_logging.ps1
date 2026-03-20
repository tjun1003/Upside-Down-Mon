#!/usr/bin/env powershell

# RAG Debug Helper Script
# 用于快速测试和调试MongoDB Atlas RAG功能

Write-Host "`n" + ("="*70) -ForegroundColor Cyan
Write-Host "📊 MongoDB Atlas RAG Logger Diagnostic" -ForegroundColor Cyan
Write-Host ("="*70) -ForegroundColor Cyan

# Check if backend is running
Write-Host "`n🔍 Checking if backend service is running..." -ForegroundColor Yellow

$backendResponse = $null
try {
    $backendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "✅ Backend is running on http://127.0.0.1:8000" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend is NOT running" -ForegroundColor Red
    Write-Host "`n   Start backend with: npm run start:all" -ForegroundColor Yellow
    exit 1
}

# Test queries
Write-Host "`n" + ("="*70) -ForegroundColor Cyan
Write-Host "🧪 Testing RAG Retrieval with Sample Queries" -ForegroundColor Cyan
Write-Host ("="*70) -ForegroundColor Cyan

$testQueries = @(
    @{
        query = "我想知道教育局的最新资讯"
        lang = "zh"
        desc = "Chinese education query"
    },
    @{
        query = "How to apply for housing assistance"
        lang = "en"
        desc = "English housing query"
    },
    @{
        query = "医疗补助申请"
        lang = "zh"
        desc = "Chinese healthcare subsidy query"
    }
)

foreach ($test in $testQueries) {
    Write-Host "`n─────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "Test: $($test.desc)" -ForegroundColor Cyan
    Write-Host "Query: '$($test.query)'" -ForegroundColor White
    Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
    
    try {
        $body = @{
            session_id = "test-rag-logging-$(Get-Random)"
            message = $test.query
            target_lang = "auto"
            assistant_mode = $true
        } | ConvertTo-Json
        
        Write-Host "`n📤 Sending request to /chat/stream..." -ForegroundColor Yellow
        
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/chat/stream" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 30
        
        Write-Host "`n📥 Response received:" -ForegroundColor Green
        
        # Parse streaming response
        $lines = $response.Content -split "`n"
        $tokenCount = 0
        $foundMeta = $false
        
        foreach ($line in $lines) {
            if ($line -like "data: *") {
                $json = $line.Substring(6).Trim()
                if ($json.StartsWith('{')) {
                    try {
                        $obj = $json | ConvertFrom-Json
                        
                        if ($obj.type -eq 'meta') {
                            $foundMeta = $true
                            Write-Host "   Source Language: $($obj.src_lang)" -ForegroundColor Green
                            Write-Host "   Target Language: $($obj.tgt_lang)" -ForegroundColor Green
                        }
                        elseif ($obj.type -eq 'token') {
                            $tokenCount++
                        }
                        elseif ($obj.type -eq 'done') {
                            Write-Host "   Generated $tokenCount tokens" -ForegroundColor Green
                        }
                    } catch {}
                }
            }
        }
        
        if (!$foundMeta) {
            Write-Host "   ⚠️  No response metadata received" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n" + ("="*70) -ForegroundColor Cyan
Write-Host "✅ Test Complete" -ForegroundColor Cyan
Write-Host ("="*70) -ForegroundColor Cyan

Write-Host "`n📋 Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Check the backend terminal for RAG logging output" -ForegroundColor White
Write-Host "  2. Look for lines starting with 🔍, ✅, ❌, or 📚" -ForegroundColor White
Write-Host "  3. Refer to RAG_LOGGING_GUIDE.md for detailed documentation" -ForegroundColor White
Write-Host ""
