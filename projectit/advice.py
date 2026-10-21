"""What the customer's operator should do when a reading crosses one of its meter's limits.

A meter's limits are its Above and Below triggers. The advice is the meter's own (written by a manager on the
meter) or, for the standard RO meters, the default below. Customers' readings never raise jobs (see meters), so
this is how an operator learns at once that something needs attention, and what to check first.
"""
import frappe
from frappe import _
from frappe.utils import flt

# role: (when too high, when too low), for the RO meters recognised by ro.roles().
DEFAULTS = {
    "feed_p": (_("Feed pressure is high. Look at the cartridge filter gauges: if the pressure drop across the filters is "
            "big, change the filters. If it stays high, call us."),
        _("Feed pressure is low. Check that the feed pump is running, the feed valve is fully open and there is water in "
            "the feed tank. If the plant keeps stopping, call us.")),
    "conc_p": (_("Concentrate pressure is high. Check the concentrate valve has not been closed. Do not adjust it yourself: "
            "call us."),
        _("Concentrate pressure is low. Check the feed pressure first. If the feed pressure is normal, call us.")),
    "feed_c": (_("The incoming water is saltier than usual. Has the water source changed? Tell us: the plant may need "
            "adjusting."),
        _("The incoming water is less salty than usual. No action needed, but tell us if the water source changed.")),
    "perm_c": (_("The treated water has more salt than it should. Do not use it where quality matters until it is checked. "
            "Check the TDS meter reads correctly (rinse the probe), then call us."), None),
    "perm_q": (None, _("The plant is making less water than it should. Check the feed pressure and the cartridge filters. The "
            "membranes may need cleaning: call us.")),
    "conc_q": (None, _("Concentrate flow is low: the membranes can scale. Check the concentrate valve and that the antiscalant "
            "dosing pump is running and has chemical. Call us.")),
    "temp": (_("The water is hotter than usual. The plant makes more water but lets more salt through. Tell us if it "
            "stays this hot."), _("The water is colder than usual. The plant makes a little less water: this is normal.")),
}
GENERIC = (_("This reading is above its limit. Check it again, and call us if it stays high."),
    _("This reading is below its limit. Check it again, and call us if it stays low."))


def _roles(equipment):
    from projectit import ro
    return {m.name: role for role, m in ro.roles(equipment).items()} if equipment else {}


def check(meter, value, roles=None):
    """The advice for one reading, or None when it is within the meter's limits."""
    value = flt(value)
    for row in meter.get("triggers") or []:
        if row.trigger_type == "Above" and value > flt(row.value):
            high = True
        elif row.trigger_type == "Below" and value < flt(row.value):
            high = False
        else:
            continue
        role = (roles or {}).get(meter.name)
        own = meter.get("advice_high") if high else meter.get("advice_low")
        default = DEFAULTS.get(role, (None, None))[0 if high else 1]
        return {"meter": meter.name, "meter_name": meter.meter_name, "unit": meter.unit or "", "value": value,
            "direction": "high" if high else "low", "limit": flt(row.value),
            "text": own or default or GENERIC[0 if high else 1]}
    return None


def for_readings(equipment, values):
    """Advice for the readings just logged ({meter: value})."""
    roles = _roles(equipment)
    out = []
    for name, value in values.items():
        found = check(frappe.get_doc("Techy Meter", name), value, roles)
        if found:
            out.append(found)
    return out


def current(equipment):
    """Advice for the machine's latest reading of each meter (the dashboard)."""
    roles = _roles(equipment)
    out = []
    for name in frappe.get_all("Techy Meter", filters={"equipment": equipment, "active": 1}, pluck="name"):
        meter = frappe.get_doc("Techy Meter", name)
        if meter.last_reading_on:
            found = check(meter, meter.last_reading, roles)
            if found:
                out.append({**found, "on": meter.last_reading_on})
    return out
