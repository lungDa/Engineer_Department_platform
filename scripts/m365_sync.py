import os
import sys
import requests


TENANT_ID = os.environ["M365_TENANT_ID"].strip()
CLIENT_ID = os.environ["M365_CLIENT_ID"].strip()
CLIENT_SECRET = os.environ["M365_CLIENT_SECRET"].strip()
WEBHOOK_TOKEN = os.environ["M365_WEBHOOK_TOKEN"].strip()

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
                "\nMicrosoft Graph 人員資料取得失敗"
                f"\nHTTP 狀態：{response.status_code}"
                f"\n錯誤代碼：{graph_error.get('code', 'unknown_error')}"
                f"\n錯誤說明：{graph_error.get('message', '無詳細說明')}"
            )

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
    print("開始取得 Microsoft 365 登入權杖……")
    access_token = get_graph_access_token()
    print("Microsoft 365 登入權杖取得成功")

    print("開始讀取 Microsoft 365 人員資料……")
    graph_users = get_m365_users(access_token)
    platform_users = transform_users(graph_users)

    if not platform_users:
        raise RuntimeError(
            "Microsoft Graph 未取得可同步的人員資料"
        )

    print("開始同步人員資料至開發工程部平台……")
    result = sync_to_platform(platform_users)

    print(f"Microsoft Graph 取得：{len(graph_users)} 人")
    print(f"符合同步條件：{len(platform_users)} 人")
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
