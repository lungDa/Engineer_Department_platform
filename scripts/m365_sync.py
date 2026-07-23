import os
import sys
import requests


TENANT_ID = os.environ["M365_TENANT_ID"]
CLIENT_ID = os.environ["M365_CLIENT_ID"]
CLIENT_SECRET = os.environ["M365_CLIENT_SECRET"]
WEBHOOK_TOKEN = os.environ["M365_WEBHOOK_TOKEN"]

SYNC_API_URL = (
    "https://engineer-department-platform.onrender.com"
    "/api/m365/users/sync"
)


def get_graph_access_token():
    url = (
        f"https://login.microsoftonline.com/"
        f"{TENANT_ID}/oauth2/v2.0/token"
    )

    response = requests.post(
        url,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    response.raise_for_status()

    return response.json()["access_token"]


def get_m365_users(access_token):
    url = (
        "https://graph.microsoft.com/v1.0/users"
        "?$select=id,displayName,mail,userPrincipalName,"
        "department,jobTitle,mobilePhone,accountEnabled,userType"
        "&$top=999"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    users = []

    while url:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        users.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return users


def transform_users(users):
    result = []

    for user in users:
        # 排除停用帳號及外部來賓
        if user.get("accountEnabled") is False:
            continue

        if user.get("userType") == "Guest":
            continue

        name = (user.get("displayName") or "").strip()
        upn = (user.get("userPrincipalName") or "").strip()
        email = (user.get("mail") or upn).strip()

        if not name or not email:
            continue

        result.append(
            {
                "name": name,
                "email": email,
                "upn": upn,
                "department": (
                    user.get("department") or ""
                ).strip(),
                "job_title": (
                    user.get("jobTitle") or ""
                ).strip(),
                "mobile": (
                    user.get("mobilePhone") or ""
                ).strip(),
                "m365_id": user.get("id") or "",
            }
        )

    return result


def sync_to_platform(users):
    response = requests.post(
        SYNC_API_URL,
        headers={
            "X-M365-Webhook-Token": WEBHOOK_TOKEN,
            "Content-Type": "application/json",
        },
        json=users,
        timeout=120,
    )
    response.raise_for_status()

    return response.json()


def main():
    access_token = get_graph_access_token()
    graph_users = get_m365_users(access_token)
    platform_users = transform_users(graph_users)

    if not platform_users:
        raise RuntimeError("Microsoft Graph 未取得可同步的人員資料")

    result = sync_to_platform(platform_users)

    print(f"Microsoft Graph 取得：{len(graph_users)} 人")
    print(f"符合同步條件：{len(platform_users)} 人")
    print(f"平台同步結果：{result}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"M365 人員同步失敗：{error}", file=sys.stderr)
        sys.exit(1)
