#!/bin/bash
set -e

# Load environment variables from .env in parent directory
if [ -f ../.env ]; then
    set -a
    source ../.env
    set +a
    echo "✅ Loaded environment variables from ../.env"
else
    echo "❌ .env file not found. Please run get-keys.sh first."
    exit 1
fi

echo "🚀 Starting data seeding..."

# Install required Python packages
echo "📦 Installing required Python packages..."
pip3 install azure-cosmos azure-search-documents requests --quiet

# Create Python script to handle the data import
cat > seed_data.py << 'EOF'
import json
import os
from azure.cosmos import CosmosClient, PartitionKey
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchableField
from azure.core.credentials import AzureKeyCredential

def load_json_data(file_path):
    """Load data from JSON or JSONL file"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Check if it's a JSONL file (one JSON object per line)
            if file_path.endswith('.jsonl'):
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            else:
                # Regular JSON file - load entire content
                content = json.load(f)
                # If it's a dict (like ml_predictions.json), convert to list of items
                if isinstance(content, dict):
                    data = [{"id": k, "value": v} for k, v in content.items()]
                # If it's already a list, use it as is
                elif isinstance(content, list):
                    data = content
                else:
                    data = [content]
        print(f"✅ Loaded {len(data)} records from {file_path}")
        return data
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return []

def setup_cosmos_db():
    """Set up Cosmos DB database and containers for each file in the data folder"""
    print("📦 Setting up Cosmos DB...")
    
    # Initialize Cosmos client
    cosmos_client = CosmosClient(os.environ['COSMOS_ENDPOINT'], os.environ['COSMOS_KEY'])
    
    # Create database
    database_name = "FinancialComplianceDB"
    try:
        database = cosmos_client.create_database_if_not_exists(id=database_name)
        print(f"✅ Database '{database_name}' ready")
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return None, None
    
    # Dynamically create containers for each file in the data folder
    data_folder = "data"
    import glob
    import os as pyos
    container_clients = {}
    for file_path in glob.glob(f"{data_folder}/*.json*"):
        file_name = pyos.path.basename(file_path)
        container_name = file_name.replace('.jsonl', '').replace('.json', '').replace('_', '').capitalize()  # e.g. customers.json -> Customers
        partition_key = '/id'
        try:
            container = database.create_container_if_not_exists(
                id=container_name,
                partition_key=PartitionKey(path=partition_key)
            )
            container_clients[container_name] = container
            print(f"✅ Container '{container_name}' ready")
        except Exception as e:
            print(f"❌ Error creating container {container_name}: {e}")
    
    return database, container_clients

def seed_cosmos_data(container_clients):
    """Seed data into Cosmos DB containers"""
    print("📦 Seeding Cosmos DB data...")
    import glob
    import os as pyos
    data_folder = "data"
    for file_path in glob.glob(f"{data_folder}/*.json*"):
        file_name = pyos.path.basename(file_path)
        container_name = file_name.replace('.jsonl', '').replace('.json', '').replace('_', '').capitalize()
        if container_name in container_clients:
            data = load_json_data(file_path)
            if data:
                container = container_clients[container_name]
                success_count = 0
                for item in data:
                    try:
                        # Ensure document has an id
                        if 'id' not in item:
                            # Try to infer id field
                            for key in ['transaction_id', 'customer_id', 'id']:
                                if key in item:
                                    item['id'] = str(item[key])
                                    break
                            else:
                                item['id'] = f'{container_name.lower()}_{success_count}'
                        container.create_item(body=item)
                        success_count += 1
                    except Exception as e:
                        if "Conflict" not in str(e):  # Ignore conflicts (already exists)
                            print(f"⚠️ Error inserting item into {container_name}: {e}")
                print(f"✅ Imported {success_count} items into {container_name}")

def setup_search_service():
    """Set up Azure AI Search indexes"""
    print("🔍 Setting up Azure AI Search...")
    
    search_endpoint = f"https://{os.environ['SEARCH_SERVICE_NAME']}.search.windows.net"
    credential = AzureKeyCredential(os.environ['SEARCH_ADMIN_KEY'])
    
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    
    # Create indexes
    indexes = ['regulations-policies']
    
    for index_name in indexes:
        try:
            # Define index schema
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String"),
                SearchableField(name="title", type="Edm.String"),
                SimpleField(name="category", type="Edm.String", filterable=True)
            ]
            
            index = SearchIndex(name=index_name, fields=fields)
            index_client.create_or_update_index(index)
            print(f"✅ Index '{index_name}' ready")
        except Exception as e:
            print(f"❌ Error creating index {index_name}: {e}")
    
    return search_endpoint, credential

def seed_search_data(search_endpoint, credential):
    """Seed data into Azure AI Search indexes"""
    print("🔍 Seeding Azure AI Search data...")
    
    # Data file mappings
    index_mappings = {
        'regulations-policies': 'data/regulations.jsonl'
    }
    
    for index_name, file_path in index_mappings.items():
        data = load_json_data(file_path)
        if data:
            search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
            
            # Prepare documents for upload
            documents = []
            for i, item in enumerate(data):
                doc = {
                    "id": str(item.get('id', f'{index_name}_{i}')),
                    "content": str(item.get('content', item.get('text', json.dumps(item)))),
                    "title": str(item.get('title', item.get('name', f'Document {i+1}'))),
                    "category": str(item.get('category', item.get('type', 'general')))
                }
                documents.append(doc)
            
            try:
                result = search_client.upload_documents(documents=documents)
                success_count = sum(1 for r in result if r.succeeded)
                print(f"✅ Uploaded {success_count} documents to {index_name}")
            except Exception as e:
                print(f"❌ Error uploading to {index_name}: {e}")

def main():
    """Main function to orchestrate the data seeding"""
    # Check required environment variables
    required_vars = ['COSMOS_ENDPOINT', 'COSMOS_KEY', 'SEARCH_SERVICE_NAME', 'SEARCH_ADMIN_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return
    
    # Set up Cosmos DB
    database, container_clients = setup_cosmos_db()
    if container_clients:
        seed_cosmos_data(container_clients)
    
    # Set up Azure AI Search
    search_endpoint, credential = setup_search_service()
    if search_endpoint and credential:
        seed_search_data(search_endpoint, credential)
    
    print("✅ Data seeding completed successfully!")

if __name__ == "__main__":
    main()
EOF

# Run the Python script
echo "🐍 Running data seeding script..."
python3 seed_data.py

# Clean up
rm seed_data.py

echo "✅ Seeding complete!"
