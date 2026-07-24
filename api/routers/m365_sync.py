import os
import sys
import requests


TENANT_ID = os.environ["M365_TENANT_ID"].strip()
CLIENT_ID = os.environ["M365_CLIENT_ID"].strip()
CLIENT_SECRET = os.environ["M365_CLIENT_SECRET"].strip()
WEBHOOK_TOKEN = os.environ["M365_WEBHOOK_TOKEN"].strip()
GROUP_ID = os.environ["M365_GROUP_ID"].strip()

PLATFORM_DEPARTMENT = "工程一部"

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

    if not response.ok:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        error_code = error_data.get("error", "unknown_error")
        error_description = error_data.get(
            "error_description",
            "Microsoft 未提供詳細錯誤內容",
        )
        trace_id = error_data.get("trace_id", "")
        correlation_id = error_data.get("correlation_id", "")
        timestamp = error_data.get("timestamp", "")

        raise RuntimeError(
            "\nMicrosoft 登入權杖取得失敗"
            f"\nHTTP 狀態：{response.status_code}"
            f"\n錯誤類型：{error_code}"
            f"\n錯誤說明：{error_description}"
            f"\nTrace ID：{trace_id}"
            f"\nCorrelation ID：{correlation_id}"
            f"\n時間：{timestamp}"
        )

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Microsoft 回應成功，但沒有取得 access_token"
        )

    return access_token


def get_m365_group_users(access_token):
    url = (
        "https://graph.microsoft.com/v1.0/"
        f"groups/{GROUP_ID}/transitiveMembers/"
        "microsoft.graph.user"
        "?$select=id,displayName,mail,userPrincipalName,"
        "jobTitle,mobilePhone,accountEnabled,userType"
        "&$top=999"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    users = []

    while url:
        response = requests.get(
            url,
            headers=headers,
            timeout=60,
        )

        if not response.ok:
            try:
                error_data = response.json()
                graph_error = error_data.get("error", {})
            except ValueError:
                graph_error = {}

            raise RuntimeError(
                "\nMicrosoft Graph 群組成員取得失敗"
                f"\n群組 ID：{GROUP_ID}"
                f"\nHTTP 狀態：{response.status_code}"
                f"\n錯誤代碼："
                f"{graph_error.get('code', 'unknown_error')}"
                f"\n錯誤說明："
                f"{graph_error.get('message', '無詳細說明')}"
            )

        data = response.json()
        users.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return users


def transform_users(users):
    result = []

    for user in users:
        # 排除停用帳號
        if user.get("accountEnabled") is False:
            continue

        # 排除外部來賓
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
                "department": PLATFORM_DEPARTMENT,
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

    if not response.ok:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {
                "detail": response.text[:500]
            }

        raise RuntimeError(
            "\n平台人員同步失敗"
            f"\nHTTP 狀態：{response.status_code}"
            f"\n平台回應：{error_data}"
        )

    return response.json()


def main():
    if not GROUP_ID:
        raise RuntimeError(
            "M365_GROUP_ID 未設定或內容為空白"
        )

    print("開始取得 Microsoft 365 登入權杖……")
    access_token = get_graph_access_token()
    print("Microsoft 365 登入權杖取得成功")

    print("開始讀取工程一部群組成員……")
    print(f"Microsoft 365 群組 ID：{GROUP_ID}")

    graph_users = get_m365_group_users(access_token)
    platform_users = transform_users(graph_users)

    if not platform_users:
        raise RuntimeError(
            "Microsoft Graph 未取得可同步的工程一部人員"
        )

    print("開始同步工程一部人員至開發工程部平台……")
    result = sync_to_platform(platform_users)

    print(f"群組取得成員：{len(graph_users)} 人")
    print(f"符合同步條件：{len(platform_users)} 人")
    print(f"平台部門設定：{PLATFORM_DEPARTMENT}")
    print(f"平台同步結果：{result}")


if __name__ == "__main__":
    try:
        main()
    except requests.Timeout:
        print(
            "M365 人員同步失敗：連線逾時，請稍後再試",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.RequestException as error:
        print(
            f"M365 人員同步失敗：網路請求錯誤：{error}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as error:
        print(
            f"M365 人員同步失敗：{error}",
            file=sys.stderr,
        )
        sys.exit(1)
