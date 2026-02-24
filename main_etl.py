from etl.crawler import AsyncNewsCrawler
import sys

def main():
    print("🚀 STARTING CUSTOM ETL PIPELINE (Async)")
    print("==================================================")
    
    try:
        # Initialize Crawler with 5 workers (Safe for 8GB RAM)
        crawler = AsyncNewsCrawler(max_workers=5)
        
        # Run Crawler
        crawler.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping ETL Pipeline...")
        crawler.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ETL Error: {e}")
        sys.exit(1)
    finally:
        crawler.shutdown()

if __name__ == "__main__":
    main()
