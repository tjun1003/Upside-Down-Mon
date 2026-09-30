"""
PDF upload functionality test script

Usage:
    python test_pdf_upload.py <pdf_file_path>
"""
import sys
import base64
import json
import requests


def test_pdf_upload(pdf_path: str, api_url: str = "http://localhost:8000", use_gridfs: bool = True):
    """Test PDF upload to knowledge base functionality"""
    
    print(f"📄 Reading PDF: {pdf_path}")
    
    # Read PDF file
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
    except FileNotFoundError:
        print(f"❌ Error: File not found: {pdf_path}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    print(f"📊 File size: {file_size_mb:.2f} MB")
    
    # Base64 encoding
    print("🔄 Encoding to Base64...")
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Prepare request
    filename = pdf_path.split('/')[-1].split('\\')[-1]
    payload = {
        'pdf_content': pdf_base64,
        'filename': filename,
        'lang': 'en',
        'entity': 'test',
        'chunk_size': 1000,
        'chunk_overlap': 200,
        'store_original': use_gridfs,  # Whether to store to GridFS
        'additional_metadata': {
            'test': True,
            'uploaded_by': 'test_script'
        }
    }
    
    print(f"📤 Uploading to {api_url}/kb/add-pdf...")
    if use_gridfs:
        print("   📦 GridFS storage: ENABLED")
    else:
        print("   📦 GridFS storage: DISABLED")
    
    try:
        response = requests.post(
            f'{api_url}/kb/add-pdf',
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Upload successful!")
            print(f"📝 Filename: {result.get('filename')}")
            print(f"📊 File size: {result.get('file_size_mb')} MB")
            print(f"📦 Chunks created: {result.get('chunks_created')}")
            print(f"💾 Chunks added to MongoDB: {result.get('chunks_added_to_mongo')}")
            print(f"🔍 KB ready: {result.get('kb_ready')}")
            
            # GridFS information
            if result.get('original_pdf_stored'):
                print(f"\n📦 GridFS Storage:")
                print(f"   - File ID: {result.get('gridfs_file_id')}")
                print(f"   - Status: ✅ Stored")
                print(f"   - Download URL: {api_url}/kb/pdf/{result.get('gridfs_file_id')}")
            else:
                print(f"\n📦 GridFS Storage: ❌ Not stored")
            
            if 'pdf_metadata' in result:
                metadata = result['pdf_metadata']
                print(f"\n📋 PDF Metadata:")
                print(f"   - Pages: {metadata.get('num_pages')}")
                print(f"   - Text length: {metadata.get('text_length')} chars")
                print(f"   - Content hash: {metadata.get('content_hash')}")
            
            return True
        else:
            print(f"\n❌ Upload failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to {api_url}")
        print("   Make sure the API server is running!")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_health_check(api_url: str = "http://localhost:8000"):
    """Test API health status"""
    print(f"🏥 Checking API health at {api_url}/health...")
    
    try:
        response = requests.get(f'{api_url}/health', timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ API is healthy!")
            print(f"   - Status: {health.get('status')}")
            print(f"   - Model loaded: {health.get('model_loaded')}")
            print(f"   - MongoDB connected: {health.get('mongo_connected')}")
            print(f"   - Atlas KB ready: {health.get('atlas_kb_ready')}")
            return True
        else:
            print(f"⚠️  API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {api_url}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_upload.py <pdf_file_path> [api_url] [--no-gridfs]")
        print("\nExample:")
        print("  python test_pdf_upload.py sample.pdf")
        print("  python test_pdf_upload.py sample.pdf http://localhost:8000")
        print("  python test_pdf_upload.py sample.pdf http://localhost:8000 --no-gridfs")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    api_url = "http://localhost:8000"
    use_gridfs = True
    
    # Parse arguments
    for arg in sys.argv[2:]:
        if arg == "--no-gridfs":
            use_gridfs = False
        elif arg.startswith("http"):
            api_url = arg
    
    print("=" * 60)
    print("PDF Upload Test Script (with GridFS support)")
    print("=" * 60)
    print()
    
    # First check API health status
    if not test_health_check(api_url):
        print("\n⚠️  API health check failed. Continuing anyway...")
    
    print("\n" + "=" * 60)
    print()
    
    # Test PDF upload
    success = test_pdf_upload(pdf_path, api_url, use_gridfs)
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed!")
    else:
        print("❌ Tests failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
