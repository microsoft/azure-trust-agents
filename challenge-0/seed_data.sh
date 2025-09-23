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

def load_jsonl_data(file_path):
    """Load data from JSONL file"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        print(f"✅ Loaded {len(data)} records from {file_path}")
        return data
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return []

def setup_cosmos_db():
    """Set up Cosmos DB database and containers"""
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
    
    # Create containers
    containers = {
        'Transactions': '/id',
        'Rules': '/id', 
        'Alerts': '/id',
        'AuditReports': '/id'
    }
    
    container_clients = {}
    for container_name, partition_key in containers.items():
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
    
    # Data file mappings
    data_mappings = {
        'Transactions': 'data/transactions.jsonl',
        'Rules': 'data/rules.jsonl',
        'Alerts': 'data/alerts.jsonl', 
        'AuditReports': 'data/audit_reports.jsonl'
    }
    
    for container_name, file_path in data_mappings.items():
        if container_name in container_clients:
            data = load_jsonl_data(file_path)
            if data:
                container = container_clients[container_name]
                success_count = 0
                for item in data:
                    try:
                        # Ensure document has an id
                        if 'id' not in item:
                            # Try different id fields based on container
                            if container_name == 'Transactions':
                                item['id'] = str(item.get('transactionId', f'tx_{success_count}'))
                            elif container_name == 'Rules':
                                item['id'] = str(item.get('ruleId', f'rule_{success_count}'))
                            elif container_name == 'Alerts':
                                item['id'] = str(item.get('alertId', f'alert_{success_count}'))
                            elif container_name == 'AuditReports':
                                item['id'] = str(item.get('reportId', f'report_{success_count}'))
                        
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
    indexes = ['regulations-policies', 'case-explanations']
    
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
        'regulations-policies': 'data/regulations.jsonl',
        'case-explanations': 'data/case_explanations.jsonl'
    }
    
    for index_name, file_path in index_mappings.items():
        data = load_jsonl_data(file_path)
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
