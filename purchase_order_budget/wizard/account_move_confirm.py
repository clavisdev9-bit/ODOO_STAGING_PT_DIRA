from odoo import models, fields


class AccountMovePostConfirmWizard(models.TransientModel):
    _name = "account.move.post.confirm.wizard"
    _description = "Account Move Post Confirmation Wizard"

    move_ids = fields.Many2many("account.move")

    def action_confirm(self):
        return self.move_ids.with_context(
            skip_post_confirm_wizard=True
        ).action_post()
