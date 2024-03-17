import boto3

def download_file_from_s3(bucket_name, key, local_file_path):
    """
    Download file from S3 bucket and save it locally.
    """
    s3 = boto3.client('s3')
    try:
        s3.download_file(bucket_name, key, local_file_path)
        print(f"File downloaded from S3 bucket '{bucket_name}' with key '{key}' to '{local_file_path}'")
    except Exception as e:
        print(f"Error downloading file from S3: {e}")

def main():
    # Replace these values with your own
    bucket_name = 'aeroglowmapupdates'
    key = 'metar.py'  # Specify the key of the file in your bucket
    local_file_path = '/home/jcramer/metar.py'  # Local path where you want to save the downloaded file
    
    # Download the file from S3
    download_file_from_s3(bucket_name, key, local_file_path)

if __name__ == "__main__":
    main()
