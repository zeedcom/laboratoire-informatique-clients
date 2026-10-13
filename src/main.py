"""
Tenders app - Flet 1.0
Run:   pip install "flet>=1.0" httpx
       flet run main.py            (desktop)
       flet run main.py --web      (web)
       flet build apk / ipa / windows / macos / linux
"""
import flet as ft
import httpx

# ---------------------------------------------------------------- CONFIG ----
BASE_URL = "https://laboinfo.pythonanywhere.com"          # Android emulator: http://10.0.2.2:8000
LOGIN_URL = "/api/auth/token/"                   # SimpleJWT (change if you use another auth)
TENDERS_URL = "/api/tenders/"
DOCUMENTS_URL = "/api/tender-documents/"
BIDS_URL = "/api/bid-submissions/"


# ------------------------------------------------------------- API CLIENT ---
class Api:
    def __init__(self):
        self.headers = {}

    async def login(self, username: str, password: str):
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(BASE_URL + LOGIN_URL, json={"username": username, "password": password})
            r.raise_for_status()
            data = r.json()
        if "access" in data:
            self.headers = {"Authorization": f"Bearer {data['access']}"}
        else:
            self.headers = {"Authorization": f"Token {data['token']}"}

    async def get(self, path: str, params: dict | None = None):
        params = {k: v for k, v in (params or {}).items() if v}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(BASE_URL + path, params=params, headers=self.headers)
            r.raise_for_status()
            data = r.json()
        # supports paginated and non-paginated DRF responses
        return data["results"] if isinstance(data, dict) and "results" in data else data

    async def post(self, path: str, payload: dict):
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(BASE_URL + path, json=payload, headers=self.headers)
            if r.status_code >= 400:
                raise Exception(r.text)
            return r.json()


api = Api()

STATUS_COLORS = {
    "accepted": ft.Colors.GREEN,
    "won": ft.Colors.GREEN,
    "rejected": ft.Colors.RED,
    "lost": ft.Colors.RED,
    "pending": ft.Colors.ORANGE,
    "submitted": ft.Colors.BLUE,
}


def val(v, default="-"):
    return default if v in (None, "") else str(v)


# -------------------------------------------------------------------- APP ---
async def main(page: ft.Page):
    page.title = "Tenders"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.padding = 0

    def toast(msg: str):
        page.show_dialog(ft.SnackBar(ft.Text(msg)))

    def info_row(icon, text, **kw):
        return ft.Row(
            [ft.Icon(icon, size=16, color=ft.Colors.GREY_700), ft.Text(text, expand=True, **kw)],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ------------------------------------------------------------ LOGIN ----
    def show_login():
        page.clean()
        page.appbar = None
        page.floating_action_button = None

        username = ft.TextField(label="Username", autofocus=True)
        password = ft.TextField(label="Password", password=True, can_reveal_password=True)
        error = ft.Text(color=ft.Colors.RED)
        btn = ft.Button("Login", icon=ft.Icons.LOGIN, width=300)

        async def do_login(e):
            btn.disabled = True
            error.value = ""
            page.update()
            try:
                await api.login(username.value, password.value)
                show_home()
                await load_tenders()
            except Exception as ex:
                error.value = f"Login failed: {ex}"
                btn.disabled = False
                page.update()

        btn.on_click = do_login
        password.on_submit = do_login

        page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.GAVEL, size=64, color=ft.Colors.INDIGO),
                        ft.Text("Tenders", size=28, weight=ft.FontWeight.BOLD),
                        ft.Container(width=300, content=ft.Column([username, password])),
                        btn,
                        error,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    spacing=16,
                ),
            )
        )

    # ------------------------------------------------------------- HOME ----
    ref_filter = ft.TextField(label="Reference", expand=True, dense=True, on_submit=lambda e: page.run_task(load_tenders))
    org_filter = ft.TextField(label="Organization", expand=True, dense=True, on_submit=lambda e: page.run_task(load_tenders))
    tenders_list = ft.ListView(expand=True, spacing=10, padding=ft.Padding.all(12))
    loader = ft.ProgressBar(visible=False)

    async def apply_filters(e):
        await load_tenders()

    async def clear_filters(e):
        ref_filter.value = ""
        org_filter.value = ""
        await load_tenders()

    filters_panel = ft.Container(
        visible=False,
        padding=ft.Padding.all(12),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Column(
            [
                ft.Row([ref_filter, org_filter]),
                ft.Row(
                    [
                        ft.TextButton("Clear", icon=ft.Icons.CLEAR, on_click=clear_filters),
                        ft.Button("Apply", icon=ft.Icons.CHECK, on_click=apply_filters),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            tight=True,
        ),
    )

    def toggle_filters(e):
        filters_panel.visible = not filters_panel.visible
        page.update()

    def tender_card(t: dict) -> ft.Card:
        docs_count = len(t.get("documents") or [])

        async def open_url(url):
            await page.launch_url(url)

        links = []
        if t.get("file_url"):
            links.append(ft.TextButton("File", icon=ft.Icons.ATTACH_FILE, on_click=lambda e, u=t["file_url"]: page.run_task(open_url, u)))
        if t.get("source_url"):
            links.append(ft.TextButton("Source", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e, u=t["source_url"]: page.run_task(open_url, u)))

        return ft.Card(
            elevation=2,
            content=ft.Container(
                padding=ft.Padding.all(16),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.DESCRIPTION, color=ft.Colors.INDIGO),
                                ft.Text(val(t.get("reference")), weight=ft.FontWeight.BOLD, size=16, expand=True),
                                ft.Chip(label=ft.Text(f"{docs_count} docs")),
                            ]
                        ),
                        info_row(ft.Icons.BUSINESS, val(t.get("organization"))),
                        info_row(ft.Icons.CALENDAR_TODAY, f"Published: {val(t.get('publication_date'))}"),
                        info_row(ft.Icons.EVENT_BUSY, f"Deadline: {val(t.get('deadline'))}", color=ft.Colors.RED_700),
                        info_row(ft.Icons.LOCATION_ON, val(t.get("address"))),
                        ft.Text(
                            val(t.get("description"), ""),
                            max_lines=3,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.GREY_800,
                        ),
                        ft.Row(
                            [
                                ft.Row(links, spacing=0),
                                ft.Button(
                                    "Bid Submissions",
                                    icon=ft.Icons.ASSIGNMENT_TURNED_IN,
                                    on_click=lambda e, tender=t: page.run_task(show_bids, tender),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            wrap=True,
                        ),
                    ],
                    spacing=6,
                ),
            ),
        )

    async def load_tenders():
        loader.visible = True
        page.update()
        try:
            data = await api.get(
                TENDERS_URL,
                {"reference": ref_filter.value, "organization": org_filter.value},
            )
            tenders_list.controls = [tender_card(t) for t in data] or [
                ft.Container(ft.Text("No tenders found"), alignment=ft.Alignment.CENTER, padding=40)
            ]
        except Exception as ex:
            toast(f"Error: {ex}")
        loader.visible = False
        page.update()

    # ------------------------------------------------------ ADD TENDER ----
    def open_add_tender(e):
        reference = ft.TextField(label="Reference *")
        organization = ft.TextField(label="Organization *")
        publication_date = ft.TextField(label="Publication date (YYYY-MM-DD)")
        deadline = ft.TextField(label="Deadline (YYYY-MM-DD)")
        address = ft.TextField(label="Address")
        description = ft.TextField(label="Description", multiline=True, min_lines=2, max_lines=4)
        file_url = ft.TextField(label="File URL")
        source_url = ft.TextField(label="Source URL")

        async def save(e):
            payload = {
                "reference": reference.value,
                "organization": organization.value,
                "publication_date": publication_date.value,
                "deadline": deadline.value,
                "address": address.value,
                "description": description.value,
                "file_url": file_url.value,
                "source_url": source_url.value,
            }
            payload = {k: v for k, v in payload.items() if v}  # skip empty fields
            try:
                await api.post(TENDERS_URL, payload)
                page.pop_dialog()
                toast("Tender created")
                await load_tenders()
            except Exception as ex:
                toast(f"Error: {ex}")

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("New tender"),
                content=ft.Column(
                    [reference, organization, publication_date, deadline, address, description, file_url, source_url],
                    tight=True,
                    width=380,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                    ft.Button("Save", icon=ft.Icons.SAVE, on_click=save),
                ],
            )
        )

    def show_home():
        page.clean()
        page.appbar = ft.AppBar(
            title=ft.Text("Tenders"),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            actions=[
                ft.IconButton(ft.Icons.FILTER_LIST, tooltip="Filters", on_click=toggle_filters),
                ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: page.run_task(load_tenders)),
                ft.IconButton(ft.Icons.LOGOUT, tooltip="Logout", on_click=lambda e: show_login()),
            ],
        )
        # fixed bottom-right "+" button
        page.floating_action_button = ft.FloatingActionButton(icon=ft.Icons.ADD, on_click=open_add_tender)
        page.floating_action_button_location = ft.FloatingActionButtonLocation.END_FLOAT
        page.add(loader, filters_panel, tenders_list)

    # -------------------------------------------------------- BIDS PAGE ----
    def bid_card(b: dict, doc: dict) -> ft.Card:
        status = str(b.get("status") or "").lower()
        return ft.Card(
            content=ft.Container(
                padding=ft.Padding.all(14),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"Bid #{b.get('id')}", weight=ft.FontWeight.BOLD, expand=True),
                                ft.Chip(
                                    label=ft.Text(status.upper() or "-", color=ft.Colors.WHITE),
                                    bgcolor=STATUS_COLORS.get(status, ft.Colors.GREY),
                                ),
                            ]
                        ),
                        info_row(ft.Icons.DESCRIPTION, f"Tender: {val(b.get('tender_reference'))}"),
                        info_row(ft.Icons.FOLDER, f"Document: {val(doc.get('reference'))}"),
                        info_row(ft.Icons.PAYMENTS, f"Price: {val(doc.get('price'))}"),
                        info_row(ft.Icons.CALENDAR_TODAY, f"Date: {val(b.get('date'))}"),
                    ],
                    spacing=4,
                ),
            )
        )

    async def show_bids(tender: dict):
        page.clean()
        page.floating_action_button = None
        page.appbar = ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: (show_home(), page.run_task(load_tenders)),
            ),
            title=ft.Text(f"Bids - {val(tender.get('reference'))}"),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
        )
        bids_list = ft.ListView(expand=True, spacing=10, padding=ft.Padding.all(12))
        bar = ft.ProgressBar()
        page.add(bar, bids_list)
        page.update()
        try:
            # documents are already nested in the tender serializer
            for doc in tender.get("documents") or []:
                bids = await api.get(BIDS_URL, {"tender_document": doc["id"]})
                bids_list.controls += [bid_card(b, doc) for b in bids]
            if not bids_list.controls:
                bids_list.controls.append(
                    ft.Container(ft.Text("No bid submissions"), alignment=ft.Alignment.CENTER, padding=40)
                )
        except Exception as ex:
            toast(f"Error: {ex}")
        bar.visible = False
        page.update()

    show_login()


ft.run(main)