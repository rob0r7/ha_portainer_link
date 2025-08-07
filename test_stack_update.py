#!/usr/bin/env python3
"""
Enhanced test script to verify stack force update functionality.
Replace the configuration values below with your actual settings.
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

async def test_stack_update():
    """Test the stack force update functionality with enhanced logging."""
    
    session = aiohttp.ClientSession()
    headers = {}
    
    try:
        print("🔐 Step 1: Authenticating...")
        auth_url = f"{PORTAINER_HOST}/api/auth"
        auth_payload = {"Username": USERNAME, "Password": PASSWORD}
        
        async with session.post(auth_url, json=auth_payload, ssl=False) as resp:
            print(f"   Auth response: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                token = data.get("jwt")
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                print("   ✅ Authentication successful")
            else:
                response_text = await resp.text()
                print(f"   ❌ Authentication failed: {response_text}")
                return
        
        print(f"\n📋 Step 2: Getting stacks for endpoint {ENDPOINT_ID}...")
        stacks_url = f"{PORTAINER_HOST}/api/stacks"
        
        async with session.get(stacks_url, headers=headers, ssl=False) as resp:
            print(f"   Stacks response: {resp.status}")
            if resp.status == 200:
                stacks_data = await resp.json()
                endpoint_stacks = [s for s in stacks_data if s.get("EndpointId") == ENDPOINT_ID]
                print(f"   ✅ Found {len(endpoint_stacks)} stacks for endpoint {ENDPOINT_ID}")
                
                for stack in endpoint_stacks:
                    print(f"      - {stack.get('Name')} (ID: {stack.get('Id')}, EndpointID: {stack.get('EndpointId')})")
                
                target_stack = None
                for stack in endpoint_stacks:
                    if stack.get("Name") == STACK_NAME and stack.get("EndpointId") == ENDPOINT_ID:
                        target_stack = stack
                        break
                
                if target_stack:
                    stack_id = target_stack.get("Id")
                    print(f"   ✅ Found target stack: {STACK_NAME} (ID: {stack_id}, EndpointID: {ENDPOINT_ID})")
                else:
                    print(f"   ❌ Stack '{STACK_NAME}' not found for endpoint {ENDPOINT_ID}")
                    print(f"   Available stacks for endpoint {ENDPOINT_ID}: {[s.get('Name') for s in endpoint_stacks]}")
                    return
            else:
                response_text = await resp.text()
                print(f"   ❌ Failed to get stacks: {response_text}")
                return
        
        print(f"\n📄 Step 3: Getting stack file...")
        stack_file_url = f"{PORTAINER_HOST}/api/stacks/{stack_id}/file"
        
        async with session.get(stack_file_url, headers=headers, ssl=False) as resp:
            print(f"   Stack file response: {resp.status}")
            if resp.status == 200:
                stack_file_data = await resp.json()
                stack_file_content = stack_file_data.get("StackFileContent", "")
                if stack_file_content:
                    print(f"   ✅ Retrieved stack file ({len(stack_file_content)} chars)")
                    print(f"   📄 File preview: {stack_file_content[:200]}...")
                else:
                    print(f"   ❌ No stack file content")
                    return
            else:
                response_text = await resp.text()
                print(f"   ❌ Failed to get stack file: {response_text}")
                return
        
        print(f"\n🔄 Step 4: Updating stack...")
        update_url = f"{PORTAINER_HOST}/api/stacks/{stack_id}/update?endpointId={ENDPOINT_ID}"
        update_payload = {
            "StackFileContent": stack_file_content,
            "Prune": False,
            "PullImage": True
        }
        
        print(f"   Update URL: {update_url}")
        print(f"   Update payload: {update_payload}")
        
        async with session.put(update_url, headers=headers, json=update_payload, ssl=False) as resp:
            print(f"   Update response: {resp.status}")
            if resp.status == 200:
                print("   ✅ Stack update successful!")
            else:
                response_text = await resp.text()
                print(f"   ❌ Stack update failed: {response_text}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await session.close()

if __name__ == "__main__":
    print("🧪 Enhanced Stack Force Update Test")
    print("=" * 50)
    print("⚠️  IMPORTANT: Update the configuration variables at the top!")
    print("=" * 50)
    
    # Uncomment the line below after updating the configuration
    # asyncio.run(test_stack_update())
