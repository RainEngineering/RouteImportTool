import sys
import base64
import json
import os

import asyncio
import dotenv
import aiohttp

from typing import List, Tuple, Optional


dotenv.load_dotenv(".env")


source_token = None
target_token = None


async def get_token(
    session: aiohttp.ClientSession, is_source_system: bool = True
) -> str:
    global source_token, target_token

    if is_source_system and source_token:
        return source_token
    elif not is_source_system and target_token:
        return target_token

    base_url = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_WEBCLIENT_URL")

    base_url = base_url.replace(".webclient", "")

    endpoint = f"{base_url}/uaa/oauth/token"

    username = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_USERNAME")
    password = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_PASSWORD")

    client_id = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_CLIENT_ID")
    client_secret = os.getenv(
        f"{'SOURCE' if is_source_system else 'TARGET'}_CLIENT_SECRET"
    )

    async with session.post(
        endpoint,
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        headers={
            "accept": "application/x-www-form-urlencoded",
            "authorization": f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}',
        },
    ) as response:
        response.raise_for_status()
        token = (await response.json()).get("access_token")
        token = f"Bearer {token}"

        if is_source_system:
            source_token = token
        else:
            target_token = token

        return token


def get_route_ids(path: str) -> List[str]:
    with open(path, "r") as f:
        lines = f.readlines()
    return [line.strip() for line in lines]


async def export_route(
    route_id: str, session: aiohttp.ClientSession, failed_routes: List[Tuple[str, str]]
):
    base_url = os.getenv("SOURCE_WEBCLIENT_URL")
    endpoint = f"{base_url}/erp-export-service/exportRoutes/{route_id}"

    try:
        async with session.get(
            endpoint, headers={"authorization": await get_token(session)}
        ) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        failed_routes.append((route_id, str(e)))
        return None


async def import_route(message: dict, session: aiohttp.ClientSession) -> Optional[int]:
    base_url = os.getenv("TARGET_WEBCLIENT_URL")
    endpoint = f"{base_url}/erp-scheduler-service/importOrders/importRouteJobs"

    # uncomment for demo purposes
    # message["exportMetadata"]['modelProperties'][0]['propertyValue'] += '_CRM3'

    escaped_message = json.dumps(message)

    data = dict(message=escaped_message, upgradeSegmentsDocument=False)

    try:
        async with session.post(
            endpoint, headers={"accept": "application/json", "authorization": await get_token(session, False)}, json=data
        ) as response:
            return await response.json()
    except aiohttp.ClientError as e:
        print(json.dumps(message, indent=2), str(e))
        return None


async def check_route_imports(job_ids: List[int], session: aiohttp.ClientSession):
    base_url = os.getenv("TARGET_WEBCLIENT_URL")
    endpoint = f"{base_url}/erp-scheduler-service/importOrders/importedJobs"
    params = "&".join([f"jobIds={job_id}" for job_id in job_ids])
    endpoint = f"{endpoint}?{params}"

    async with session.get(
        endpoint, headers={"authorization": await get_token(session, False)}
    ) as response:
        return await response.json()


async def main(path: str):
    route_ids = get_route_ids(path)

    if len(route_ids) == 0:
        print(f"No route ids found in {path}")
        return

    failed_routes: List[Tuple[str, str]] = []

    async with aiohttp.ClientSession(raise_for_status=True) as session:

        export_tasks = [
            export_route(route_id, session, failed_routes) for route_id in route_ids
        ]

        for route in failed_routes:
            print(f'route failed: {route}')

        route_exports = await asyncio.gather(*export_tasks)

        import_tasks = [
            import_route(route_export, session) for route_export in route_exports
        ]

        import_responses = await asyncio.gather(*import_tasks)

        job_ids = [response.get('jobId') for response in import_responses if response]

        if not job_ids:
            print("Unable to find any job ids from import response, something might have gone wrong.")
            return

        results = []

        while retry_count := 0 < 5:
            statuses = await check_route_imports(job_ids, session)

            for response in statuses:
                if response.get('responseCode'):
                    results.append(response)
                    job_ids.remove(response.get('jobId'))
            
            if len(job_ids) == 0:
                break

            await asyncio.sleep(1 * retry_count)
            retry_count += 1
        
        if len(job_ids):
            print(f"Unable to get status for job IDs {job_ids} jobs after 5 retries.")

        failed_imports = [response for response in statuses if response.get('responseCode') != 200]

        for failed_import in failed_imports:
            print(f"{failed_import.get('responseCode')} - {failed_import.get('responseMessage')}")

        if not len(failed_imports):
            print("All routes imported successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_file>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
