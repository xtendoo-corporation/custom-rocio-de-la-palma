# -*- coding: utf-8 -*-
def migrate(cr, version):
    """
    Migración para eliminar la columna brother_leave_reason_id
    que ya no es necesaria en el modelo res.partner
    """
    # Verificar si la columna existe antes de intentar eliminarla
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_partner'
        AND column_name = 'brother_leave_reason_id'
    """)

    if cr.fetchone():
        # La columna existe, proceder a eliminarla
        cr.execute("ALTER TABLE res_partner DROP COLUMN IF EXISTS brother_leave_reason_id")
        print("Columna brother_leave_reason_id eliminada de res_partner")
    else:
        print("La columna brother_leave_reason_id ya no existe en res_partner")

