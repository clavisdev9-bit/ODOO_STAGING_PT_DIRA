from odoo import fields, api, models


class TimesheetBill(models.TransientModel):
    """Timesheet Bill"""
    _name = 'timesheet.billing'
    _description = 'HR Timesheet Billing'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string="Timesheet Product")
    timesheet_ids = fields.Many2many(
        'account.analytic.line', string="Timesheets")
    date = fields.Date(default=fields.Date.today())
    vendor_id = fields.Many2one('res.partner')
    is_diff_work_order = fields.Boolean()
    is_bill_created = fields.Boolean()
    sub_category_ids = fields.Many2many('job.sub.category',
                                        compute="_compute_job_sub_categories",
                                        string="Sub Categories")
    sub_category_id = fields.Many2one('job.sub.category', string="Sub Category",
                                      domain="[('id','in',sub_category_ids)]")

    @api.model
    def default_get(self, fields_list):
        """Default get"""
        res = super().default_get(fields_list)
        default_timesheet_product_id = self.env['ir.config_parameter'].sudo().get_param(
            'tk_construction_management.construction_timesheet_product_id')
        res['product_id'] = int(
            default_timesheet_product_id) if default_timesheet_product_id else self.env.ref(
            'tk_construction_management.construction_product_2').id
        active_ids = self._context.get('active_ids')
        domain = [('id', 'in', active_ids), ('is_validate', '=', True), ('bill_id', '=', False),
                  ('job_order_id', '!=', False)]
        job_order_check = self.env['account.analytic.line'].search(domain).mapped(
            'job_order_id').mapped('id')
        if not job_order_check:
            res['is_bill_created'] = True
        elif not len(job_order_check) == 1:
            res['is_diff_work_order'] = True
        timesheet_ids = self.env['account.analytic.line'].search(
            domain).mapped('id')
        res['timesheet_ids'] = [(6, 0, timesheet_ids)]
        return res

    @api.depends('timesheet_ids')
    def _compute_job_sub_categories(self):
        """Compute Job Sub Categories"""
        for rec in self:
            ids = []
            job_order_check = rec.timesheet_ids.mapped(
                'job_order_id').mapped('id')
            if len(job_order_check) == 1:
                ids = self.env['job.order'].browse(job_order_check[0]).mapped(
                    'labour_order_ids').mapped(
                    'sub_category_id').mapped('id')
            rec.sub_category_ids = ids

    def action_move_timesheet_bill(self):
        """Move Timesheet Bill"""
        job_order_id = self.timesheet_ids.mapped('job_order_id').mapped('id')
        work_order_id = self.env['job.order'].browse(job_order_id[0])
        total_hours = sum(self.timesheet_ids.mapped('unit_amount'))
        invoice_line = []
        for data in self.timesheet_ids:
            desc = "Employee : " + \
                   str(data.employee_id.name) + "\n" + "Task : " + str(data.name)
            invoice_line.append((0, 0, {
                'product_id': self.product_id.id,
                'name': desc,
                'quantity': data.unit_amount,
                'price_unit': data.hourly_cost,
                'tax_ids': False
            }))
        invoice_id = self.env['account.move'].create({
            'partner_id': self.vendor_id.id,
            'move_type': 'in_invoice',
            'invoice_date': self.date,
            'invoice_line_ids': invoice_line,
            'bill_of': "Labour Timesheet Bill",
            'job_order_id': job_order_id[0]
        })
        self.env['order.labour.line'].create({
            'sub_category_id': self.sub_category_id.id,
            'vendor_id': self.vendor_id.id,
            'product_id': self.product_id.id,
            'name': "Internal Time Sheet Billing",
            'hours': total_hours,
            'job_order_id': work_order_id.id,
            'bill_id': invoice_id.id,
            'internal_entry': True,
            'timesheet_entry_ids': [(6, 0, self.timesheet_ids.ids)]
        })
        for data in self.timesheet_ids:
            data.bill_id = invoice_id.id
