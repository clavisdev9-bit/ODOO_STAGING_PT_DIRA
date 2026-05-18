import logging
import re
import pytz
from datetime import datetime
from odoo import http, fields
from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)


class HomeCustom(Home):
    def _login_redirect(self, uid, redirect=None):
        user = request.env['res.users'].browse(uid)
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        if tenant:
            return '/tenant/orders'

        return super(HomeCustom, self)._login_redirect(uid, redirect=redirect)

class EventCustomerController(http.Controller):
    def _normalize_phone(self, phone):
        """Normalize phone number to avoid duplicates"""
        if not phone:
            return False

        phone = re.sub(r'[^\d+]', '', phone.strip())

        if not re.match(r'^(\+62|62|0)8\d{8,12}$', phone):
            return False

        if phone.startswith("08"):
            phone = "+62" + phone[1:]
        elif phone.startswith("628"):
            phone = "+62" + phone[2:]
        elif phone.startswith("8"):
            phone = "+62" + phone

        return phone

    @http.route('/register', type='http', auth='public', website=True)
    def register(self, **kw):
        return request.render('amazing_toy_show_2.register_page')

    @http.route('/register/submit', type='http', auth='public', website=True, csrf=True)
    def register_submit(self, **post):
        name = (post.get('name') or '').strip()
        phone = (post.get('phone') or '').strip()
        email = (post.get('email') or '').strip()
        age = post.get('age')
        gender = post.get('gender')

        def redirect_with_data(error_code):
            return request.render('amazing_toy_show_2.register_page', {
                'error': error_code,
                'prev_data': post
            })

        if not name or not phone or not email:
            return redirect_with_data('missing')

        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return redirect_with_data('invalid_phone')

        try:
            customer = request.env['res.partner'].sudo()
            if customer.search_count([('phone', '=', normalized_phone)], limit=1):
                return redirect_with_data('phone_exists')

            if customer.search_count([('email', '=', email)], limit=1):
                return redirect_with_data('email_exists')

            partner = request.env['res.partner'].sudo().create({
                'name': name,
                'phone': normalized_phone,
                'email': email,
                'age': int(age or 0),
                'gender': gender,
            })

            request.session['partner_id'] = partner.id
            request.session['user'] = {
                'name': partner.name,
                'phone': partner.phone,
                'email': partner.email,
                'age': partner.age,
                'gender': partner.gender,
            }

            return request.redirect('/tenants')

        except Exception as e:
            _logger.exception("Error during registration: %s", str(e))
            return request.redirect('/register?error=server')

    @http.route('/login', type='http', auth='public', website=True)
    def login(self, **kw):
        return request.render('amazing_toy_show_2.login_page')

    @http.route('/login/submit', type='http', auth='public', website=True, csrf=True)
    def login_submit(self, **post):
        phone = (post.get('phone') or '').strip()
        email = (post.get('email') or '').strip()

        def redirect_with_data(error_code):
            return request.render('amazing_toy_show_2.login_page', {
                'error': error_code,
                'prev_data': post
            })

        normalized_phone = self._normalize_phone(phone)

        if not normalized_phone:
            return redirect_with_data('invalid_phone')

        partner = request.env['res.partner'].sudo().search([
            ('phone', '=', normalized_phone),
            ('email', '=ilike', email)
        ], limit=1)

        if not partner:
            return redirect_with_data('not_found')

        request.session['partner_id'] = partner.id
        request.session['user'] = {
            'name': partner.name,
            'phone': partner.phone,
            'email': partner.email,
            'age': partner.age or 0,
            'gender': partner.gender,
        }

        return request.redirect('/tenants')

    @http.route('/tenants', type='http', auth='public', website=True)
    def browse_tenant(self, **kwargs):
        if not request.session.get('partner_id'):
            return request.redirect('/login')

        partner_id = request.session.get('partner_id')
        order = request.env['event.order'].get_or_create_cart(partner_id)
        floor = kwargs.get('floor')
        search = kwargs.get('search')
        domain = []

        if floor:
            domain.append(('floor', '=', floor))

        if search:
            domain.append(('name', 'ilike', search))

        tenants = request.env['event.tenant'].sudo().search(domain, order="name asc")
        result = {}
        floor_map = {
            'ug': 'UG - Upper Ground',
            'gf': 'GF - Ground Floor',
            '2nd': '2nd Floor',
        }

        for t in tenants:
            floor_key = t.floor or 'other'
            floor_name = floor_map.get(floor_key, floor_key)

            if floor_key not in result:
                result[floor_key] = {
                    'label': floor_name,
                    'tenants': []
                }

            result[floor_key]['tenants'].append(t)

        return request.render('amazing_toy_show_2.browse_tenant_page', {
            'floors': result,
            'selected_floor': floor,
            'search': search,
            'order': order,
        })

    @http.route('/tenant/<int:tenant_id>', type='http', auth='public', website=True)
    def tenant_products(self, tenant_id, search=None, **kwargs):
        tenant = request.env['event.tenant'].sudo().browse(tenant_id)

        if not request.session.get('partner_id'):
            return request.redirect('/login')

        if not tenant.exists():
            return request.redirect('/tenants')

        domain = [
            ('sale_ok', '=', True),
            ('tenant_id', '=', tenant_id)
        ]

        if search:
            domain.append(('name', 'ilike', search))

        products = request.env['product.product'].sudo().search(domain, order="name asc")

        return request.render('amazing_toy_show_2.tenant_products_page', {
            'tenant': tenant,
            'products': products,
            'search': search,
        })

    @http.route('/tenant/<int:tenant_id>/product/<int:product_id>', type='http', auth='public', website=True)
    def product_detail(self, tenant_id, product_id, **kwargs):
        if not request.session.get('partner_id'):
            return request.redirect('/login')

        product = request.env['product.product'].sudo().browse(product_id)
        tenant = request.env['event.tenant'].sudo().browse(tenant_id)

        partner_id = request.session.get('partner_id')
        order = request.env['event.order'].get_or_create_cart(partner_id)

        return request.render('amazing_toy_show_2.product_detail_page', {
            'product': product,
            'tenant': tenant,
            'order': order,
        })

    def _get_cart(self):
        partner_id = request.session.get('partner_id')
        return request.env['event.order'].get_or_create_cart(partner_id)

    @http.route('/cart', type='http', auth='public', website=True)
    def cart(self, **kw):
        if not request.session.get('partner_id'):
            return request.redirect('/login')

        order = self._get_cart()
        return request.render('amazing_toy_show_2.cart_page', {'order': order})

    @http.route('/cart/add', type='json', auth='public', website=True)
    def add_to_cart(self, **kwargs):
        try:
            product_id = int(kwargs.get('product_id'))
            qty = max(1, int(kwargs.get('qty', 1)))
        except (TypeError, ValueError):
            return {'status': 'error', 'message': 'Invalid format'}

        order = self._get_cart()
        product = request.env['product.product'].sudo().browse(product_id)
        if not product.exists():
            return {'status': 'error', 'message': 'Product not found'}

        if product.qty_available < qty:
            return {
                'status': 'error',
                'message': f'Not enough stock! Stock available: {int(product.qty_available)}'
            }

        line = request.env['event.order.line'].sudo().search([
            ('order_id', '=', order.id),
            ('product_id', '=', product.id)
        ], limit=1)

        if line:
            if product.qty_available < (line.qty + qty):
                return {'status': 'error', 'message': 'Total in cart exceeds available stock'}
            line.qty += qty
        else:
            request.env['event.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'tenant_id': product.tenant_id.id,
                'qty': qty,
                'price_unit': product.lst_price,
            })

        return {
            'cart_qty': order.cart_qty,
            'total_qty': order.total_qty,
            'total_amount': order.total_amount
        }

    @http.route('/cart/update_qty', type='json', auth='public', website=True)
    def update_cart_qty(self, line_id, direction, **kwargs):
        partner_id = request.session.get('partner_id')
        line = request.env['event.order.line'].sudo().browse(int(line_id))
        if not line.exists() or line.order_id.partner_id.id != partner_id:
            return {'status': 'error', 'message': 'Unauthorized'}

        if direction == 'plus':
            if line.qty < line.product_id.qty_available:
                line.qty += 1
            else:
                return {
                    'status': 'limit_reached',
                    'message': 'Not enough stock',
                    'current_qty': line.qty
                }
        elif direction == 'minus':
            if line.qty > 1:
                line.qty -= 1
            else:
                order = line.order_id
                line.unlink()
                return {
                    'status': 'removed',
                    'total_amount': order.total_amount,
                    'cart_qty': order.cart_qty
                }

        return {
            'status': 'success',
            'new_qty': line.qty,
            'subtotal': line.subtotal,
            'total_amount': line.order_id.total_amount,
            'cart_qty': line.order_id.cart_qty
        }

    @http.route('/cart/checkout', type='json', auth='public', website=True)
    def cart_checkout(self, **kwargs):
        order = self._get_cart()
        if not order or not order.line_ids:
            return {'status': 'error', 'message': 'Your cart is empty'}

        success = order.action_checkout()
        if success:
            return {
                'status': 'success',
                'redirect': f'/checkout/success/{order.token}'
            }
        else:
            return {
                'status': 'empty',
                'message': 'All items were out of stock and removed from your cart.'
            }

    @http.route('/cart/delete_line', type='json', auth='public', website=True)
    def delete_cart_line(self, line_id):
        line = request.env['event.order.line'].sudo().browse(int(line_id))
        partner_id = request.session.get('partner_id')
        if line.exists() and line.order_id.partner_id.id == partner_id:
            order = line.order_id
            line.unlink()
            return {
                'status': 'success',
                'total_amount': order.total_amount,
                'cart_qty': order.cart_qty
            }

        return {'status': 'error'}

    @http.route('/checkout/success/<string:token>', type='http', auth='public', website=True)
    def checkout_success(self, token, **kwargs):
        order = request.env['event.order'].sudo().search([('token', '=', token)], limit=1)
        if not order:
            return request.not_found()

        checkout_url = order.get_checkout_url()
        return request.render('amazing_toy_show_2.checkout_qr_page', {
            'order': order,
            'checkout_url': checkout_url,
        })

    @http.route('/checkout/edit_order', type='json', auth='public', website=True)
    def edit_order(self, order_id):
        order = request.env['event.order'].sudo().browse(int(order_id))
        if order.exists() and order.state == 'confirmed':
            order.action_set_to_draft()
            return {'status': 'success', 'redirect': '/cart'}

        return {'status': 'error', 'message': 'Order cannot be edited.'}

    @http.route('/checkout/check_status/<string:token>', type='json', auth='public', website=True)
    def check_payment_status(self, token):
        order = request.env['event.order'].sudo().search([('token', '=', token)], limit=1)
        if order:
            return {
                'state': order.state,
                'is_paid': order.state == 'paid'
            }
        return {'status': 'error'}

    @http.route('/checkout/paid_success/<string:token>', type='http', auth='public', website=True)
    def checkout_paid_success(self, token, **kwargs):
        order = request.env['event.order'].sudo().search([
            ('token', '=', token),
            ('state', '=', 'paid'),
        ], limit=1)
        if not order:
            return request.redirect('/cart')

        date_paid_jakarta = False
        if order.date_paid:
            tz = pytz.timezone('Asia/Jakarta')
            date_paid_jakarta = order.date_paid.astimezone(tz)

        return request.render('amazing_toy_show_2.customer_success_page', {
            'order': order,
            'date_paid_jakarta': date_paid_jakarta,
        })

    @http.route('/checkout/pickup_status/<string:token>', type='http', auth='public', website=True)
    def checkout_pickup_status(self, token, **kwargs):
        order = request.env['event.order'].sudo().search([('token', '=', token)], limit=1)
        if not order:
            return request.redirect('/tenants')

        return request.render('amazing_toy_show_2.customer_pickup_tracking_page', {
            'order': order,
        })

    @http.route('/checkout/pickup_status/check', type='json', auth='public', website=True)
    def check_pickup_status_json(self, token):
        order = request.env['event.order'].sudo().search([('token', '=', token)], limit=1)
        if not order:
            return {'status': 'error'}

        handover_count = len(order.line_ids.filtered(lambda l: l.is_handed_over))
        total_count = len(order.line_ids)

        return {
            'handover_count': handover_count,
            'total_count': total_count,
            'all_done': handover_count == total_count and total_count > 0
        }

    @http.route('/receipt/digital/<string:token>', type='http', auth="public", website=True)
    def digital_receipt(self, token, **kwargs):
        order = request.env['event.order'].sudo().search([
            ('token', '=', token),
            ('state', 'in', ['paid', 'done'])
        ], limit=1)

        if not order:
            return request.redirect('/tenants')

        date_paid_jakarta = False
        if order.date_paid:
            tz = pytz.timezone('Asia/Jakarta')
            date_paid_jakarta = order.date_paid.astimezone(tz)

        return request.render('amazing_toy_show_2.digital_receipt_layout', {
            'order': order,
            'date_paid_jakarta': date_paid_jakarta,
        })

class EventCashierController(http.Controller):
    @http.route('/cashier/login', type='http', auth='public', website=True)
    def cashier_login(self, **kw):
        return request.render('amazing_toy_show_2.cashier_login_page')

    @http.route('/cashier/login/submit', type='http', auth='public', website=True, csrf=True)
    def cashier_submit(self, **post):
        pin = post.get('pin')
        cashier = request.env['event.cashier'].sudo().search([('pin', '=', pin), ('is_active', '=', True)], limit=1)
        if not cashier:
            return request.redirect('/cashier/login?error=1')

        request.session['cashier_id'] = cashier.id
        request.session['cashier_name'] = cashier.name
        request.session['cashier_code'] = cashier.code

        return request.redirect('/cashier')

    @http.route('/cashier/logout', type='http', auth='public', website=True)
    def cashier_logout(self):
        request.session.pop('cashier_id', None)
        return request.redirect('/cashier/login')

    @http.route('/cashier', type='http', auth='public', website=True)
    def cashier_scan(self, **kw):
        cashier_id = request.session.get('cashier_id')
        if not cashier_id:
            return request.redirect('/cashier/login')

        cashier_id = request.env['event.cashier'].sudo().browse(cashier_id)

        return request.render('amazing_toy_show_2.cashier_scan_page', {
            'cashier_id': cashier_id,
        })

    @http.route('/cashier/get_order_details', type='json', auth='public', website=True)
    def get_order_details(self, search_val):
        if not request.session.get('cashier_id'):
            return {'status': 'error', 'message': 'Session Expired'}

        search_val = search_val.strip()
        order = request.env['event.order'].sudo().search([
            ('name', '=', search_val)
        ], limit=1)
        if not order:
            return {'status': 'error', 'message': 'Transaction not found'}

        if order.state == 'draft':
            return {'status': 'invalid', 'message': 'Transaction Time Out'}

        if order.state in ['paid', 'done']:
            return {'status': 'paid', 'message': 'Transaction already paid'}

        if order.state == 'confirmed':
            return {
                'status': 'success',
                'order_id': order.id
            }

        return {'status': 'error', 'message': 'Invalid transaction'}

    @http.route('/cashier/review/<int:order_id>', type='http', auth='public', website=True)
    def cashier_review(self, order_id, **kw):
        if not request.session.get('cashier_id'):
            return request.redirect('/cashier/login')

        order = request.env['event.order'].sudo().browse(order_id)
        if not order.exists() or order.state != 'confirmed':
            return request.redirect('/cashier')

        return request.render('amazing_toy_show_2.cashier_review_page', {
            'order': order,
            'cashier_name': request.session.get('cashier_name')
        })

    @http.route('/cashier/payment/<int:order_id>', type='http', auth='public', website=True)
    def cashier_payment(self, order_id, **kw):
        if not request.session.get('cashier_id'):
            return request.redirect('/cashier/login')

        order = request.env['event.order'].sudo().browse(order_id)
        if not order.exists() or order.state != 'confirmed':
            return request.redirect('/cashier')

        return request.render('amazing_toy_show_2.cashier_payment_page', {
            'order': order,
            'cashier_name': request.session.get('cashier_name')
        })

    @http.route('/cashier/validate_payment', type='json', auth='public', website=True)
    def validate_payment(self, order_id, method, received, change):
        if not request.session.get('cashier_id'):
            return {'status': 'error', 'message': 'Session Expired'}

        order = request.env['event.order'].sudo().browse(int(order_id))
        if order.exists() and order.state == 'confirmed':
            order.write({
                'state': 'paid',
                'payment_method': method,
                'amount_received': received,
                'amount_change': change,
                'cashier_id': request.session.get('cashier_id'),
                'date_paid': fields.Datetime.now()
            })
            return {'status': 'success'}

        return {'status': 'error', 'message': 'Transaction time out or already paid'}

    @http.route('/cashier/print_receipt/<int:order_id>', type='http', auth='public', website=True)
    def print_receipt(self, order_id, **kw):
        order = request.env['event.order'].sudo().browse(order_id)
        if not order.exists():
            return "Order not found"

        date_paid_jakarta = False
        if order.date_paid:
            tz = pytz.timezone('Asia/Jakarta')
            date_paid_jakarta = order.date_paid.astimezone(tz)

        return request.render('amazing_toy_show_2.report_cashier_receipt', {
            'order': order,
            'date_paid_jakarta': date_paid_jakarta,
        })

    @http.route('/cashier/recap', type='http', auth='public', website=True)
    def cashier_recap(self, date_str=None, **kw):
        cashier_id = request.session.get('cashier_id')
        if not cashier_id:
            return request.redirect('/cashier/login')

        target_date = fields.Date.from_string(date_str) if date_str else fields.Date.today()
        start_date = datetime.combine(target_date, datetime.min.time())
        end_date = datetime.combine(target_date, datetime.max.time())
        orders = request.env['event.order'].sudo().search([
            ('cashier_id', '=', cashier_id),
            ('state', 'in', ['paid', 'done']),
            ('date_paid', '>=', start_date),
            ('date_paid', '<=', end_date),
        ])
        total_sales = sum(orders.mapped('total_amount'))
        recap_data = {
            'cash': len(orders.filtered(lambda r: r.payment_method == 'cash')),
            'qr': len(orders.filtered(lambda r: r.payment_method == 'qr')),
            'card': len(orders.filtered(lambda r: r.payment_method == 'card'))
        }

        return request.render('amazing_toy_show_2.cashier_recap_page', {
            'orders_count': len(orders),
            'total_sales': total_sales,
            'recap': recap_data,
            'cashier_name': request.session.get('cashier_name'),
            'shift_time': "08:00 – 16:00",  # Bisa ditarik dari database jika ada model shift
            'today_val': target_date,
            'today_str': target_date.strftime('%d %b %Y')
        })

class EventTenantController(http.Controller):
    @http.route('/tenant/orders', type='http', auth="user", website=True)
    def tenant_order_list(self, **kwargs):
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        if not tenant:
            return request.redirect('/')

        filter_type = kwargs.get('filter', 'all')
        search_query = kwargs.get('search', '')
        domain = [('tenant_id', '=', tenant.id), ('order_id.state', 'in', ['paid', 'done'])]
        if search_query:
            domain += [('order_id.name', 'ilike', search_query)]

        all_lines = request.env['event.order.line'].sudo().search(domain)
        total_order_ids = all_lines.mapped('order_id')
        count_all = len(total_order_ids)
        count_ready = len(all_lines.filtered(lambda l: not l.is_handed_over).mapped('order_id'))
        count_done = len(all_lines.filtered(lambda l: l.is_handed_over).mapped('order_id'))
        if filter_type == 'ready':
            display_lines = all_lines.filtered(lambda l: not l.is_handed_over)
        elif filter_type == 'done':
            display_lines = all_lines.filtered(lambda l: l.is_handed_over)
        else:
            display_lines = all_lines

        sorted_orders = display_lines.mapped('order_id').sorted(key=lambda r: r.date_paid or r.id, reverse=True)

        return request.render('amazing_toy_show_2.tenant_order_list_page', {
            'tenant': tenant,
            'orders': sorted_orders,
            'count_all': count_all,
            'count_ready': count_ready,
            'count_done': count_done,
            'current_filter': filter_type,
            'search_query': search_query,
        })

    @http.route('/tenant/orders/check_count', type='json', auth="user", website=True)
    def check_tenant_order_count(self):
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        if not tenant:
            return {'status': 'error', 'count': 0}

        domain = [('tenant_id', '=', tenant.id), ('order_id.state', 'in', ['paid', 'done'])]
        current_count = request.env['event.order.line'].sudo().search_count(domain)

        return {
            'status': 'success',
            'count': current_count
        }

    @http.route('/tenant/order/search_by_name', type='json', auth="user", website=True)
    def search_order_by_name(self, name):
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        line = request.env['event.order.line'].sudo().search([
            ('order_id.name', '=', name),
            ('tenant_id', '=', tenant.id)
        ], limit=1)

        if line:
            return {
                'status': 'success',
                'redirect_url': f'/tenant/order/{line.order_id.id}'
            }
        return {
            'status': 'error',
            'message': 'Order not found'
        }

    @http.route('/tenant/order/<model("event.order"):order>', type='http', auth="user", website=True)
    def tenant_order_handover(self, order, **kwargs):
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        if not tenant:
            return request.redirect('/')

        order_sudo = order.sudo()
        tenant_lines = order_sudo.line_ids.filtered(lambda l: l.tenant_id.id == tenant.id)
        total_items = len(tenant_lines)
        handed_over_count = len(tenant_lines.filtered(lambda l: l.is_handed_over))
        progress = (handed_over_count / total_items * 100) if total_items > 0 else 0

        return request.render('amazing_toy_show_2.tenant_handover_page', {
            'order': order_sudo,
            'tenant': tenant,
            'lines': tenant_lines,
            'progress': progress,
            'total_items': total_items,
            'handed_over_count': handed_over_count,
        })

    @http.route('/tenant/order/complete', type='json', auth="user", website=True)
    def tenant_complete_handover(self, line_ids, **kwargs):
        if not line_ids:
            return {'status': 'error', 'message': 'No items selected'}

        lines = request.env['event.order.line'].sudo().browse(line_ids)
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)

        if tenant and all(l.tenant_id.id == tenant.id for l in lines):
            for line in lines:
                line.action_item_handover()
            return {'status': 'success'}

        return {'status': 'error', 'message': 'Unauthorized access to these items.'}

    @http.route('/tenant/dashboard', type='http', auth="user", website=True)
    def tenant_dashboard(self, date_str=None, **kwargs):
        user = request.env.user
        tenant = request.env['event.tenant'].sudo().search([('user_ids', 'in', user.id)], limit=1)
        if not tenant:
            return request.redirect('/')

        target_date = fields.Date.from_string(date_str) if date_str else fields.Date.today()
        start_date = datetime.combine(target_date, datetime.min.time())
        end_date = datetime.combine(target_date, datetime.max.time())
        lines = request.env['event.order.line'].sudo().search([
            ('tenant_id', '=', tenant.id),
            ('order_id.state', 'in', ['paid', 'done']),
            ('order_id.date_paid', '>=', start_date),
            ('order_id.date_paid', '<=', end_date)
        ])
        total_sales = sum(lines.mapped('subtotal'))
        total_orders = len(lines.mapped('order_id'))
        total_items = sum(lines.mapped('qty'))
        count_ready = len(lines.filtered(lambda l: not l.is_handed_over).mapped('order_id'))
        product_stats = {}
        for line in lines:
            p_id = line.product_id
            if p_id not in product_stats:
                product_stats[p_id] = 0
            product_stats[p_id] += line.qty


        sorted_products = sorted(product_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        top_products = []
        for product, qty in sorted_products:
            percentage = (qty / total_items * 100) if total_items > 0 else 0
            top_products.append({
                'name': product.name,
                'qty': int(qty),
                'percent': percentage
            })

        return request.render('amazing_toy_show_2.tenant_dashboard_page', {
            'tenant': tenant,
            'today_val': target_date.strftime('%Y-%m-%d'),
            'total_sales': total_sales,
            'total_orders': total_orders,
            'total_items': int(total_items),
            'pending': int(count_ready),
            'top_products': top_products,
        })

    @http.route('/tenant/logout', type='http', auth="user", website=True)
    def tenant_logout(self):
        request.session.logout()
        return request.redirect('/web/login')