import sys
import base64
import json

import asyncio
import dotenv
import aiohttp

from typing import List, Tuple


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

    base_url = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_BASE_QUERY_URL")
    endpoint = f"{base_url}/erp-export-service/token"

    username = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_USERNAME")
    password = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_PASSWORD")

    client_id = os.getenv(f"{'SOURCE' if is_source_system else 'TARGET'}_CLIENT_ID")
    client_secret = os.getenv(
        f"{'SOURCE' if is_source_system else 'TARGET'}_CLIENT_SECRET"
    )

    async with session.get(
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
    base_url = os.getenv("SOURCE_BASE_QUERY_URL")
    endpoint = f"{base_url}/erp-export-service/exportRoutes/{route_id}"

    try:
        async with session.get(
            endpoint, headers={"authorization": await get_token()}
        ) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        failed_routes.append((route_id, str(e)))
        return None


async def import_route(message: dict, session: aiohttp.ClientSession) -> int:
    base_url = os.getenv("TARGET_BASE_QUERY_URL")
    endpoint = f"{base_url}/erp-scheduler-service/importOrders/importRouteJobs"

    # TODO: this might need to change to escaped JSON string
    escaped_message = json.dumps(message)

    data = dict(message=escaped_message, upgradeSegmentsDocument=False)

    try:
        async with session.post(
            endpoint, headers={"authorization": await get_token()}, data=data
        ) as response:
            # FIXME: untested
            return (await response.json()).get("jobId")
    except aiohttp.ClientError as e:
        failed_imports.append((message, str(e)))
        return None


async def check_route_import(job_id: int, session: aiohttp.ClientSession):
    base_url = os.getenv("TARGET_BASE_QUERY_URL")
    endpoint = f"{base_url}/erp-scheduler-service/importedJobs/{job_id}/message"

    try:
        async with session.get(
            endpoint, headers={"authorization": await get_token()}
        ) as response:
            # TODO: check response in json
            # if not 200, log message and job id or route id
            return await response.json()
    except aiohttp.ClientError as e:
        failed_imports.append((message, str(e)))
        return None


async def main(path: str):
    route_ids = get_route_ids(path)

    failed_routes = []

    async with aiohttp.ClientSession(raise_for_status=True) as session:
        export_tasks = [
            export_route(route_id, session, failed_routes) for route_id in route_ids
        ]

        route_exports = await asyncio.gather(*export_tasks)

        import_tasks = [
            import_route(route_export, session) for route_export in route_exports
        ]

        job_ids = await asyncio.gather(*import_tasks)

        check_tasks = [
            check_route_import(job_id, session) for job_id in job_ids
        ]

        statuses = await asyncio.gather(*check_tasks)

        print(statuses)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_file>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
