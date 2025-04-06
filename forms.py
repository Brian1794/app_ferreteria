from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Length

class ReparacionForm(FlaskForm):
    cliente_id = SelectField('Cliente', coerce=int, validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[DataRequired(), Length(min=10)])
    electrodomestico = StringField('Electrodoméstico', validators=[DataRequired()])
    marca = StringField('Marca', validators=[DataRequired()])
    modelo = StringField('Modelo', validators=[DataRequired()])
    problema = TextAreaField('Problema', validators=[DataRequired(), Length(min=10)])
    fecha_entrega_estimada = DateField('Fecha de Entrega Estimada', format='%Y-%m-%d', validators=[DataRequired()]) 