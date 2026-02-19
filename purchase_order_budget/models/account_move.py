from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        # skip wizard jika dipanggil dari wizard
        if self.env.context.get("skip_post_confirm_wizard"):
            return super().action_post()

        # Filter hanya Vendor Bill & Customer Invoice
        moves_need_confirm = self.filtered(
            lambda m: m.move_type in ("in_invoice", "out_invoice")
        )

        if moves_need_confirm:
            return {
                "type": "ir.actions.act_window",
                "name": _("Konfirmasi Posting"),
                "res_model": "account.move.post.confirm.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_move_ids": moves_need_confirm.ids,
                },
            }

        return super().action_post()
