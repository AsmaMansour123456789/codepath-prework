from odoo import fields, models, api, _
from odoo.tools import config
from odoo.exceptions import UserError
from psycopg2.extensions import TransactionRollbackError

import logging
import re

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    project_ticket_id = fields.Many2one('project.project', string='Projet',)
    task_ticket_id = fields.Many2one('project.task', string='Tâche', domain = "[('project_id','=', project_ticket_id)]" )
