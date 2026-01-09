import sys
import os
import redis
import json

def check_task_result(task_id):
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        key = f"celery-task-meta-{task_id}"
        value = r.get(key)
        if value:
            print(f"Result for {task_id}:")
            print(json.dumps(json.loads(value), indent=2))
        else:
            print(f"No result found for {task_id}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_task_result(sys.argv[1])
    else:
        print("Please provide task ID")
