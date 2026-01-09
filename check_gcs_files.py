"""Check files in GCS buckets."""
from google.cloud import storage

def list_gcs_files():
    """List all files in the GCS buckets."""
    client = storage.Client.from_service_account_json("bosso-dev.json")
    
    buckets = ["book-translator-originals", "book-translator-outputs"]
    
    for bucket_name in buckets:
        print(f"\n📦 {bucket_name}")
        print("=" * 60)
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        
        if not blobs:
            print("   (empty)")
        else:
            for blob in blobs:
                size_kb = blob.size / 1024
                print(f"   • {blob.name} ({size_kb:.1f} KB)")
        
        print(f"   Total files: {len(blobs)}")

if __name__ == "__main__":
    list_gcs_files()
