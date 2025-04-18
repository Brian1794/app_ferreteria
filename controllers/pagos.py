from flask import current_app
from datetime import datetime
from database import get_db

class PagoController:
    @staticmethod
    def crear_pago(monto, metodo_pago, id_pedido, estado='pendiente'):
        """
        Crea un nuevo registro de pago en la base de datos
        """
        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO pagos (monto, metodo_pago, id_pedido, estado, fecha_creacion) '
                'VALUES (?, ?, ?, ?, ?)',
                (monto, metodo_pago, id_pedido, estado, datetime.now())
            )
            db.commit()
            return cursor.lastrowid
        except Exception as e:
            current_app.logger.error(f'Error al crear pago: {str(e)}')
            db.rollback()
            raise

    @staticmethod
    def actualizar_estado_pago(id_pago, nuevo_estado):
        """
        Actualiza el estado de un pago existente
        """
        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute(
                'UPDATE pagos SET estado = ?, fecha_actualizacion = ? WHERE id = ?',
                (nuevo_estado, datetime.now(), id_pago)
            )
            db.commit()
            return True
        except Exception as e:
            current_app.logger.error(f'Error al actualizar estado del pago: {str(e)}')
            db.rollback()
            raise

    @staticmethod
    def obtener_pago(id_pago):
        """
        Obtiene los detalles de un pago específico
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM pagos WHERE id = ?', (id_pago,))
        return cursor.fetchone()

    @staticmethod
    def listar_pagos_por_pedido(id_pedido):
        """
        Lista todos los pagos asociados a un pedido
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM pagos WHERE id_pedido = ? ORDER BY fecha_creacion DESC', (id_pedido,))
        return cursor.fetchall()