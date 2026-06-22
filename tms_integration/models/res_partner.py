from odoo import models, fields


class ResPartner(models.Model):
    """Ensure partner_latitude/partner_longitude are available (standard in Odoo 18)."""
    _inherit = 'res.partner'

    # partner_latitude and partner_longitude are built-in since Odoo 14.
    # We add a helper computed field to confirm geo-coding status.
    tms_geo_verified = fields.Boolean(
        'Geo-coordinates Verified', default=False,
        help='Koordinat latitude/longitude sudah diverifikasi untuk TMS routing')

    def action_tms_verify_geocode(self):
        """Quick action to flag partner geo-coordinates as verified."""
        for partner in self:
            if partner.partner_latitude and partner.partner_longitude:
                partner.tms_geo_verified = True
        return True
