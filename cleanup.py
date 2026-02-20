import os
import glob

def cleanup():
    patterns = [
        "*.png",
        "*.xlsx",
        "*.csv",
        "positions_only_report_*.md",
        "options_only_report_*.md",
        "combined_report_*.md"
    ]
    
    deleted_count = 0
    for pattern in patterns:
        files = glob.glob(pattern)
        for f in files:
            try:
                os.remove(f)
                print(f"Deleted: {f}")
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {f}: {e}")
                
    print(f"\nCleanup complete. Deleted {deleted_count} files.")

if __name__ == "__main__":
    cleanup()
