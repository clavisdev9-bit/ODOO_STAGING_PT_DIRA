from odoo import models, fields


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    tms_vehicle_type = fields.Selection([
        ('motorcycle', 'Motor'),
        ('pickup', 'Pickup'),
        ('box', 'Box Truck'),
        ('truck', 'Truck'),
    ], string='TMS Vehicle Type', index=True)

    # Capacity
    tms_max_weight = fields.Float(
        'Max Weight (kg)', digits=(8, 2),
        help='Kapasitas maksimal berat muatan dalam kg')
    tms_max_volume = fields.Float(
        'Max Volume (m³)', digits=(8, 3),
        help='Kapasitas maksimal volume muatan dalam m³')

    # Cargo dimensions
    tms_cargo_length = fields.Float('Cargo Length (cm)', digits=(7, 2))
    tms_cargo_width = fields.Float('Cargo Width (cm)', digits=(7, 2))
    tms_cargo_height = fields.Float('Cargo Height (cm)', digits=(7, 2))

    # Operational cost parameters
    tms_fuel_efficiency = fields.Float(
        'Fuel Efficiency (km/L)', digits=(5, 2),
        help='Konsumsi bahan bakar dalam km per liter')
    tms_daily_depreciation = fields.Monetary(
        'Daily Depreciation (IDR)',
        currency_field='tms_currency_id',
        help='Biaya depresiasi kendaraan per hari dalam IDR')
    tms_maint_budget = fields.Monetary(
        'Daily Maintenance Budget (IDR)',
        currency_field='tms_currency_id',
        help='Anggaran perawatan kendaraan per hari dalam IDR')
    tms_currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False))

    # TMS sync
    tms_active = fields.Boolean(
        'Active in TMS', default=True,
        help='Tandai kendaraan ini tersedia untuk dispatching di TMS')

    def _compute_tms_cargo_volume(self):
        for rec in self:
            if rec.tms_cargo_length and rec.tms_cargo_width and rec.tms_cargo_height:
                rec.tms_cargo_volume_m3 = (
                    rec.tms_cargo_length * rec.tms_cargo_width * rec.tms_cargo_height
                ) / 1_000_000
            else:
                rec.tms_cargo_volume_m3 = 0.0

    tms_cargo_volume_m3 = fields.Float(
        'Computed Cargo Volume (m³)', compute='_compute_tms_cargo_volume',
        digits=(8, 3), store=True)
