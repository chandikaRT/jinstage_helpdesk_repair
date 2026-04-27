# Phase 1: Repair diagnosis master data models
from . import repair_symptom_area
from . import repair_symptom_code
from . import repair_condition
from . import repair_diagnosis_area
from . import repair_diagnosis_code
from . import repair_reason
from . import repair_reason_customer
from . import repair_sub_reason
from . import repair_resolution

# Phase 2: Core model extensions
from . import helpdesk_ticket_type
from . import helpdesk_stage
from . import helpdesk_ticket
from . import stock_picking
from . import stock_location

# Phase 3: New model extensions
from . import repair_diagnosis_line
from . import project_task
from . import sale_order
from . import account_move
