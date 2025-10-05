#!/usr/bin/env python3
"""
Supabase Connection Test Script
Run this to verify your Supabase integration before generating episodes
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(text.center(60))
    print("=" * 60)

def test_env_variables():
    """Test that environment variables are set"""
    print_header("CHECKING ENVIRONMENT VARIABLES")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in .env file")
        return False
    else:
        print(f"✅ SUPABASE_URL found: {supabase_url}")
    
    if not supabase_key:
        print("❌ SUPABASE_ANON_KEY not found in .env file")
        return False
    else:
        print(f"✅ SUPABASE_ANON_KEY found: {supabase_key[:20]}...")
    
    return True

def test_connection():
    """Test connection to Supabase"""
    print_header("TESTING SUPABASE CONNECTION")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    try:
        endpoint = f"{supabase_url}/rest/v1/episodes?limit=1"
        headers = {
            'apikey': supabase_key,
            'Content-Type': 'application/json'
        }
        
        print(f"📡 Connecting to: {endpoint}")
        response = requests.get(endpoint, headers=headers, timeout=5)
        
        print(f"📥 Response status: {response.status_code}")
        
        response.raise_for_status()
        
        data = response.json()
        
        print("✅ Connection successful!")
        
        if data:
            print(f"✅ Found {len(data)} episode(s) in database")
            print(f"\nMost recent episode:")
            print(f"   Title: {data[0].get('title', 'N/A')}")
            print(f"   Date: {data[0].get('date', 'N/A')}")
            print(f"   Episode #: {data[0].get('episode_number', 'N/A')}")
        else:
            print("ℹ️  No episodes in database yet (that's okay!)")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error {e.response.status_code}")
        print(f"\nResponse: {e.response.text}")
        
        if e.response.status_code in [401, 403]:
            print("\n💡 This looks like a Row Level Security (RLS) issue.")
            print("   Solutions:")
            print("   1. Go to Supabase → Authentication → Policies")
            print("   2. Find the 'episodes' table")
            print("   3. Either:")
            print("      - Disable RLS (for testing)")
            print("      - Add policy: Allow anonymous SELECT/INSERT")
        
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Supabase")
        print("   Check your SUPABASE_URL is correct")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_table_structure():
    """Test that the episodes table has the right columns"""
    print_header("CHECKING TABLE STRUCTURE")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    try:
        # Try to get one row to see the structure
        endpoint = f"{supabase_url}/rest/v1/episodes?limit=1"
        headers = {
            'apikey': supabase_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(endpoint, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        required_columns = ['title', 'date', 'description', 'link', 'episode_number']
        
        if data and len(data) > 0:
            existing_columns = list(data[0].keys())
            print(f"✅ Table exists with columns: {', '.join(existing_columns)}")
            
            missing = [col for col in required_columns if col not in existing_columns]
            if missing:
                print(f"⚠️  Missing columns: {', '.join(missing)}")
                print("   You may need to alter your table to add these columns")
                return False
            else:
                print("✅ All required columns present!")
                return True
        else:
            print("ℹ️  No data to check structure (table might be empty)")
            print("   Will test by trying to insert...")
            return True
            
    except Exception as e:
        print(f"⚠️  Could not check structure: {e}")
        return True  # Don't fail on this

def test_insert():
    """Test inserting a record"""
    print_header("TESTING INSERT")
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    try:
        endpoint = f"{supabase_url}/rest/v1/episodes"
        
        # Create test data
        test_data = {
            "title": "🧪 Test Episode - DELETE ME",
            "date": datetime.now().strftime("%B %d, %Y").upper(),
            "description": "This is a test episode created by test_supabase.py. You can safely delete it.",
            "link": "https://demetri.xyz/test",
            "episode_number": 99999  # Use a high number to avoid conflicts
        }
        
        headers = {
            'apikey': supabase_key,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        
        print("📤 Attempting to insert test episode...")
        print(f"   Title: {test_data['title']}")
        print(f"   Episode #: {test_data['episode_number']}")
        
        response = requests.post(
            endpoint,
            json=test_data,
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        
        result = response.json()
        
        print("✅ Insert successful!")
        
        if result and len(result) > 0:
            print(f"   Database ID: {result[0].get('id', 'N/A')}")
        
        print("\n⚠️  IMPORTANT: Delete the test episode from Supabase:")
        print("   1. Go to Supabase → Table Editor → episodes")
        print("   2. Find row with episode_number = 99999")
        print("   3. Delete it")
        print("   OR run this SQL:")
        print("   DELETE FROM episodes WHERE episode_number = 99999;")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Insert failed: HTTP {e.response.status_code}")
        print(f"\nResponse: {e.response.text}")
        
        if e.response.status_code in [401, 403]:
            print("\n💡 RLS is blocking inserts.")
            print("   Fix:")
            print("   1. Go to Supabase → Authentication → Policies")
            print("   2. Find 'episodes' table")
            print("   3. Add policy:")
            print("      CREATE POLICY \"Allow anonymous inserts\"")
            print("      ON episodes FOR INSERT TO anon")
            print("      WITH CHECK (true);")
        
        return False
        
    except Exception as e:
        print(f"❌ Insert failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n")
    print("🧪 SUPABASE INTEGRATION TEST SUITE")
    print("=" * 60)
    
    # Test 1: Environment variables
    if not test_env_variables():
        print("\n❌ FAILED: Environment variables not set")
        print("\n📝 Add these to your .env file:")
        print("   SUPABASE_URL=https://YOUR_PROJECT.supabase.co")
        print("   SUPABASE_ANON_KEY=your_anon_key_here")
        return
    
    # Test 2: Connection
    if not test_connection():
        print("\n❌ FAILED: Could not connect to Supabase")
        print("\n💡 Check:")
        print("   1. SUPABASE_URL is correct")
        print("   2. SUPABASE_ANON_KEY is correct")
        print("   3. Your internet connection")
        print("   4. Supabase project is active")
        return
    
    # Test 3: Table structure
    test_table_structure()
    
    # Test 4: Insert
    if not test_insert():
        print("\n❌ FAILED: Could not insert test data")
        return
    
    # All tests passed
    print_header("ALL TESTS PASSED! ✅")
    print("\n🎉 Your Supabase integration is working correctly!")
    print("\n📝 Next steps:")
    print("   1. Delete the test episode from Supabase")
    print("   2. Run: python main.py test.txt")
    print("   3. Check Supabase for your real episode!")
    print("\n")

if __name__ == "__main__":
    main()