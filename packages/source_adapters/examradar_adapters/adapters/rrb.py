"""RRB board pages list each CEN with the sections it has. Section pages sit behind a firewall that rejects
automated requests, so we never fetch them: a new CEN or a new section is published as a fast alert that links
to the official page, and dates come from manual entry by an admin."""

from urllib.parse import parse_qs, urlparse

from ..base import Adapter, CycleHint, Item, Listing, clean, soup_of
from ..normalise import normalise_url

SECTION_KIND = {
    "indicative notice": "upcoming_notice", "notification": "notification", "application (special notice)": "notification",
    "city intimation (exam)": "exam_city", "e-call letters": "admit_card", "exam schedule": "schedule",
    "exam results": "result", "objection tracker": "answer_key", "document verification": "document_verification",
    "medical examination": "document_verification", "selection list": "result", "special notice on examination": "notice",
}


class RRB(Adapter):
    key = "rrb"
    sector = "railway"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        items: dict[str, Item] = {}
        board = urlparse(listing.url).path.strip("/").split("/")[0] or "rrb"
        for a in soup_of(body).find_all("a", href=True):
            if "getdata" not in a["href"]:
                continue
            href = normalise_url(a["href"], base_url)
            q = parse_qs(urlparse(href).query)
            cen, section = (q.get("cennum") or [""])[0], (q.get("category") or [""])[0]
            if not cen or not section:
                continue
            key = f"{board}|{cen}|{section}"
            hint = CycleHint(exam_slug=f"rrb-cen-{cen.replace('/', '-')}", exam_name=f"RRB CEN {cen}",
                             title=f"RRB CEN {cen}", sector="railway", year=int(cen[-4:]) if cen[-4:].isdigit() else None,
                             notification_number=f"CEN {cen}")
            items[key] = Item(key=key, title=f"RRB {board.title()}: CEN {cen} - {clean(section)}", url=href,
                              kind=SECTION_KIND.get(section.lower(), "notice"), cycle=hint,
                              data={"cen": cen, "section": section, "fetch": False})
        return list(items.values())
