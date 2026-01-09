"""Setup Google Cloud Storage buckets for the book translator."""
from google.cloud import storage
import os

def setup_gcs_buckets():
    """Create GCS buckets if they don't exist."""
    
    # Initialize client
    credentials_path = "bosso-dev.json"
    project_id = "bosso-dev"
    
    print(f"🔧 Initializing GCS client with project: {project_id}")
    client = storage.Client.from_service_account_json(credentials_path)
    
    # Bucket names
    buckets_to_create = [
        "book-translator-originals",
        "book-translator-outputs"
    ]
    
    for bucket_name in buckets_to_create:
        try:
            # Check if bucket exists
            bucket = client.bucket(bucket_name)
            if bucket.exists():
                print(f"✅ Bucket already exists: {bucket_name}")
            else:
                # Create bucket
                bucket = client.create_bucket(bucket_name, location="US")
                print(f"✅ Created bucket: {bucket_name}")
                
                # Set CORS for web access (optional)
                bucket.cors = [{
                    "origin": ["*"],
                    "method": ["GET", "HEAD", "PUT", "POST"],
                    "responseHeader": ["Content-Type"],
                    "maxAgeSeconds": 3600
                }]
                bucket.patch()
                print(f"   ↳ CORS configured")
                
        except Exception as e:
            print(f"❌ Error with bucket {bucket_name}: {e}")
            if "403" in str(e):
                print(f"   ↳ Permission denied. Make sure service account has 'Storage Admin' role")
            elif "409" in str(e):
                print(f"   ↳ Bucket name taken globally. Try: {bucket_name}-{project_id}")
    
    print("\n🎉 GCS setup complete!")
    print("\nTo enable GCS uploads, update backend/.env:")
    print("USE_LOCAL_STORAGE=false")
    
    # List existing buckets
    print("\n📦 Your GCS buckets:")
    for bucket in client.list_buckets():
        print(f"   • {bucket.name}")

if __name__ == "__main__":
    setup_gcs_buckets()
