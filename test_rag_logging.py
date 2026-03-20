#!/usr/bin/env python3
"""
Test script to verify RAG logging is working.
This script tests the RAG retrieval with detailed logging output.
"""

import sys
import os

# Add the API directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'app', 'api', 'translate'))

from translation_config import logger, USE_ATLAS_KB, ATLAS_URI, ATLAS_DB_NAME
from chatbot_core import KnowledgeBase

def test_rag_logging():
    """Test RAG logging functionality"""
    
    print("\n" + "="*70)
    print("🧪 TESTING RAG LOGGING")
    print("="*70 + "\n")
    
    # Check configuration
    print(f"Configuration:")
    print(f"  - USE_ATLAS_KB: {USE_ATLAS_KB}")
    print(f"  - MongoDB URI: {'✓ Configured' if ATLAS_URI else '❌ Not configured'}")
    print(f"  - MongoDB DB: {ATLAS_DB_NAME if ATLAS_DB_NAME else '❌ Not configured'}")
    print()
    
    if not USE_ATLAS_KB:
        print("❌ MongoDB Atlas KB is disabled (USE_ATLAS_KB=0)")
        print("   To test RAG logging, set USE_ATLAS_KB=1 in .env\n")
        return
    
    if not ATLAS_URI or not ATLAS_DB_NAME:
        print("❌ MongoDB configuration is incomplete")
        print("   Please check MONGODB_ATLAS_URI and MONGODB_ATLAS_DB in .env\n")
        return
    
    # Initialize KB
    print("Initializing Knowledge Base...")
    kb = KnowledgeBase()
    
    if not kb.ready:
        print("❌ Knowledge Base is not ready")
        print("   Please check MongoDB connection and configuration\n")
        return
    
    print("✅ Knowledge Base initialized successfully\n")
    
    # Test queries
    test_queries = [
        "教育局最新资讯",
        "医疗补助申请",
        "housing assistance Malaysia",
        "government services",
    ]
    
    for query in test_queries:
        print(f"\n{'─'*70}")
        print(f"Testing query: '{query}'")
        print(f"{'─'*70}")
        
        context = kb.retrieve(query, top_k=3)
        
        if context:
            print(f"\n✅ Retrieved context (first 200 chars):")
            print(f"   {context[:200]}...")
        else:
            print(f"\n❌ No context retrieved")
    
    print("\n" + "="*70)
    print("🧪 TEST COMPLETE")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_rag_logging()
