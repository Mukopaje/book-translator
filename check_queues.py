import redis

def check_queues():
    try:
        r = redis.Redis(host='localhost', port=6380, db=0)
        print("Connected to Redis")
        
        keys = r.keys('*')
        print(f"All keys: {keys}")
        
        for queue in ['celery', 'translation']:
            length = r.llen(queue)
            print(f"Queue '{queue}' length: {length}")
            if length > 0:
                print(f"  Contents of '{queue}':")
                items = r.lrange(queue, 0, -1)
                for item in items:
                    print(f"    {item}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_queues()
