#!/usr/bin/env python3
"""
Test script to manually verify Portainer API calls for stack force update.
Replace the configuration values below with your actual Portainer settings.
"""

import asyncio
import aiohttp
import json

# Configuration - REPLACE WITH YOUR ACTUAL VALUES
PORTAINER_HOST = "http://your-portainer-host:9000"  # Replace with your Portainer URL
ENDPOINT_ID = 1  # Replace with your endpoint ID
STACK_NAME = "filebrowser"  # Replace with your stack name
USERNAME = "your-username"  # Replace with your username
PASSWORD = "your-password"  # Replace with your password
# OR use API key instead:
# API_KEY = "your-api-key"

async def test_portainer_api():
    """Test the Portainer API calls manually."""
    
    # Initialize session
    session = aiohttp.ClientSession()
    headers = {}
    
    try:
        # Step 1: Authenticate
        print("🔐 Step 1: Authenticating...")
        auth_url = f"{PORTAINER_HOST}/api/auth"
        auth_payload = {"Username": USERNAME, "Password": PASSWORD}
        
        async with session.post(auth_url, json=auth_payload, ssl=False) as resp:
            print(f"   Auth response status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                token = data.get("jwt")
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                print("   ✅ Authentication successful")
            else:
                print(f"   ❌ Authentication failed: {resp.status}")
                return
        
        # Step 2: Get stacks list
        print(f"\n📋 Step 2: Getting stacks for endpoint {ENDPOINT_ID}...")
        stacks_url = f"{PORTAINER_HOST}/api/endpoints/{ENDPOINT_ID}/stacks"
        
        async with session.get(stacks_url, headers=headers, ssl=False) as resp:
            print(f"   Stacks response status: {resp.status}")
            if resp.status == 200:
                stacks_data = await resp.json()
                print(f"   ✅ Found {len(stacks_data)} stacks")
                for stack in stacks_data:
                    print(f"      - {stack.get('Name')} (ID: {stack.get('Id')})")
                
                # Find our target stack
                target_stack = None
                for stack in stacks_data:
                    if stack.get("Name") == STACK_NAME:
                        target_stack = stack
                        break
                
                if target_stack:
                    stack_id = target_stack.get("Id")
                    print(f"   ✅ Found target stack: {STACK_NAME} (ID: {stack_id})")
                else:
                    print(f"   ❌ Stack '{STACK_NAME}' not found")
                    print(f"   Available stacks: {[s.get('Name') for s in stacks_data]}")
                    return
            else:
                print(f"   ❌ Failed to get stacks: {resp.status}")
                return
        
        # Step 3: Get stack file content
        print(f"\n📄 Step 3: Getting stack file content...")
        stack_file_url = f"{PORTAINER_HOST}/api/endpoints/{ENDPOINT_ID}/stacks/{stack_id}/file"
        
        async with session.get(stack_file_url, headers=headers, ssl=False) as resp:
            print(f"   Stack file response status: {resp.status}")
            if resp.status == 200:
                stack_file_data = await resp.json()
                stack_file_content = stack_file_data.get("StackFileContent", "")
                if stack_file_content:
                    print(f"   ✅ Retrieved stack file content ({len(stack_file_content)} characters)")
                    print(f"   File preview: {stack_file_content[:200]}...")
                else:
                    print("   ❌ No stack file content found")
                    return
            else:
                print(f"   ❌ Failed to get stack file: {resp.status}")
                return
        
        # Step 4: Update stack
        print(f"\n🔄 Step 4: Updating stack...")
        update_url = f"{PORTAINER_HOST}/api/endpoints/{ENDPOINT_ID}/stacks/{stack_id}/update"
        update_payload = {
            "StackFileContent": stack_file_content,
            "prune": True,
            "pullImage": True,
            "env": [],
            "endpointId": ENDPOINT_ID
        }
        
        async with session.put(update_url, headers=headers, json=update_payload, ssl=False) as resp:
            print(f"   Update response status: {resp.status}")
            if resp.status == 200:
                print("   ✅ Stack update successful!")
            else:
                response_text = await resp.text()
                print(f"   ❌ Stack update failed: {resp.status}")
                print(f"   Response: {response_text}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await session.close()

if __name__ == "__main__":
    print("🧪 Portainer API Test Script")
    print("=" * 50)
    print("⚠️  IMPORTANT: Update the configuration variables at the top of this script!")
    print("=" * 50)
    
    # Uncomment the line below after updating the configuration
    # asyncio.run(test_portainer_api())
