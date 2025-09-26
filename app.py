from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pyodbc
from datetime import datetime
import os
import json

app = Flask(__name__)
CORS(app)

# Configuración para pyodbc (SQL Server con Windows Authentication)
def get_db_connection():
    try:
        server = r'PC\SQLEXPRESS'
        database = 'TiendaPlus'
        
        connection_string = f'''
            DRIVER={{ODBC Driver 17 for SQL Server}};
            SERVER={server};
            DATABASE={database};
            Trusted_Connection=yes;
            Encrypt=no;
            TrustServerCertificate=yes;
            Connection Timeout=30;
        '''
        
        conn = pyodbc.connect(connection_string)
        print("✅ Conexión a SQL Server exitosa con pyodbc")
        return conn
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        raise

# Inicializar la base de datos
def init_db():
    try:
        print("🔧 Inicializando base de datos...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Crear tabla de pedidos si no existe
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'pedidos')
            BEGIN
                CREATE TABLE pedidos (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    nombre NVARCHAR(100) NOT NULL,
                    grado NVARCHAR(10) NOT NULL,
                    producto NVARCHAR(100) NOT NULL,
                    cantidad INT NOT NULL,
                    detalles NVARCHAR(500),
                    fecha DATETIME2 DEFAULT SYSDATETIME()
                )
                PRINT 'Tabla pedidos creada exitosamente'
            END
        """)
        
        # Crear tabla de productos si no existe
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'productos')
            BEGIN
                CREATE TABLE productos (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    nombre NVARCHAR(100) NOT NULL,
                    categoria NVARCHAR(50) NOT NULL,
                    precio DECIMAL(10,2) NOT NULL,
                    descripcion NVARCHAR(500),
                    imagen_url NVARCHAR(500),
                    activo BIT DEFAULT 1,
                    fecha_creacion DATETIME2 DEFAULT SYSDATETIME()
                )
                PRINT 'Tabla productos creada exitosamente'
                
                -- Insertar productos de ejemplo
                INSERT INTO productos (nombre, categoria, precio, descripcion, imagen_url) VALUES
                ('Pegatina de Estrellas', 'pegatinas', 2.50, 'Pegatina con diseño de estrellas brillantes', 'https://via.placeholder.com/300x200/9c88ff/ffffff?text=Pegatina+Estrellas'),
                ('Collar de Corazón', 'collares', 8.00, 'Collar elegante con dije de corazón', 'https://via.placeholder.com/300x200/c2b5ff/ffffff?text=Collar+Corazón'),
                ('Llavero de Panda', 'llaveros', 3.00, 'Llavero adorable con forma de panda', 'https://via.placeholder.com/300x200/7b6ce0/ffffff?text=Llavero+Panda'),
                ('Pegatina de Luna', 'pegatinas', 2.75, 'Pegatina con diseño de luna y estrellas', 'https://via.placeholder.com/300x200/9c88ff/ffffff?text=Pegatina+Luna'),
                ('Collar de Perlas', 'collares', 12.00, 'Collar elegante con perlas artificiales', 'https://via.placeholder.com/300x200/c2b5ff/ffffff?text=Collar+Perlas'),
                ('Llavero de Gato', 'llaveros', 3.50, 'Llavero con forma de gatito', 'https://via.placeholder.com/300x200/7b6ce0/ffffff?text=Llavero+Gato')
            END
        """)
        
        conn.commit()
        print("✅ Base de datos inicializada correctamente")
        
    except Exception as e:
        print(f"❌ Error inicializando la base de datos: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

# Ruta principal - servir el frontend
@app.route('/')
def index():
    return render_template('index.html')

# API para verificar estado de la base de datos
@app.route('/api/sql-status')
def sql_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT @@VERSION as version")
        version = cursor.fetchone()[0]
        
        cursor.execute("SELECT DB_NAME() as current_db")
        current_db = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pedidos")
        total_pedidos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = 1")
        total_productos = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'connected',
            'server': 'PC\\SQLEXPRESS',
            'database': current_db,
            'version': version.split('\n')[0],
            'total_pedidos': total_pedidos,
            'total_productos': total_productos,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'server': 'PC\\SQLEXPRESS',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# API para obtener productos
@app.route('/api/productos', methods=['GET'])
def obtener_productos():
    try:
        categoria = request.args.get('categoria', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if categoria and categoria != 'todos':
            cursor.execute("""
                SELECT id, nombre, categoria, precio, descripcion, imagen_url 
                FROM productos 
                WHERE categoria = ? AND activo = 1
                ORDER BY nombre
            """, (categoria,))
        else:
            cursor.execute("""
                SELECT id, nombre, categoria, precio, descripcion, imagen_url 
                FROM productos 
                WHERE activo = 1
                ORDER BY categoria, nombre
            """)
        
        productos = []
        for row in cursor.fetchall():
            productos.append({
                'id': row[0],
                'nombre': row[1],
                'categoria': row[2],
                'precio': float(row[3]),
                'descripcion': row[4],
                'imagen': row[5]
            })
        
        conn.close()
        return jsonify(productos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para crear un nuevo producto (solo admin)
@app.route('/api/productos', methods=['POST'])
def crear_producto():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        # Validaciones
        required_fields = ['nombre', 'categoria', 'precio']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Campos requeridos faltantes: {", ".join(missing_fields)}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO productos (nombre, categoria, precio, descripcion, imagen_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['nombre'].strip(),
            data['categoria'],
            float(data['precio']),
            data.get('descripcion', '').strip(),
            data.get('imagen', 'https://via.placeholder.com/300x200/9c88ff/ffffff?text=' + data['nombre'].replace(' ', '+'))
        ))
        
        conn.commit()
        producto_id = cursor.fetchval()
        conn.close()
        
        return jsonify({
            'message': 'Producto creado exitosamente',
            'producto_id': producto_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

# API para actualizar un producto (solo admin)
@app.route('/api/productos/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE productos 
            SET nombre = ?, categoria = ?, precio = ?, descripcion = ?, imagen_url = ?
            WHERE id = ?
        """, (
            data.get('nombre', '').strip(),
            data.get('categoria', ''),
            float(data.get('precio', 0)),
            data.get('descripcion', '').strip(),
            data.get('imagen', ''),
            producto_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Producto actualizado exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para eliminar un producto (solo admin)
@app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # En lugar de eliminar, marcamos como inactivo
        cursor.execute("UPDATE productos SET activo = 0 WHERE id = ?", (producto_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Producto eliminado exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para crear pedidos
@app.route('/api/pedidos', methods=['POST'])
def crear_pedido():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        # Validaciones
        required_fields = ['nombre', 'grado', 'producto', 'cantidad']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Campos requeridos faltantes: {", ".join(missing_fields)}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO pedidos (nombre, grado, producto, cantidad, detalles)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['nombre'].strip(), 
            data['grado'], 
            data['producto'], 
            int(data['cantidad']), 
            data.get('detalles', '').strip()
        ))
        
        conn.commit()
        pedido_id = cursor.fetchval()
        conn.close()
        
        return jsonify({
            'message': 'Pedido creado exitosamente',
            'pedido_id': pedido_id,
            'servidor': 'PC\\SQLEXPRESS'
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

# API para obtener pedidos (solo admin)
@app.route('/api/pedidos', methods=['GET'])
def obtener_pedidos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, nombre, grado, producto, cantidad, detalles, fecha 
            FROM pedidos 
            ORDER BY fecha DESC
        """)
        
        pedidos = []
        for row in cursor.fetchall():
            pedidos.append({
                'id': row[0],
                'nombre': row[1],
                'grado': row[2],
                'producto': row[3],
                'cantidad': row[4],
                'detalles': row[5],
                'fecha': row[6].isoformat() if row[6] else None
            })
        
        conn.close()
        return jsonify(pedidos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para obtener estadísticas (solo admin)
@app.route('/api/estadisticas', methods=['GET'])
def obtener_estadisticas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total de pedidos
        cursor.execute("SELECT COUNT(*) FROM pedidos")
        total_pedidos = cursor.fetchone()[0]
        
        # Pedidos por grado
        cursor.execute("SELECT grado, COUNT(*) FROM pedidos GROUP BY grado")
        pedidos_por_grado = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Productos más vendidos
        cursor.execute("""
            SELECT producto, SUM(cantidad) as total_vendido 
            FROM pedidos 
            GROUP BY producto 
            ORDER BY total_vendido DESC
        """)
        productos_mas_vendidos = [{'producto': row[0], 'total': row[1]} for row in cursor.fetchall()]
        
        # Total de productos activos
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = 1")
        total_productos = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_pedidos': total_pedidos,
            'pedidos_por_grado': pedidos_por_grado,
            'productos_mas_vendidos': productos_mas_vendidos,
            'total_productos': total_productos
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Iniciando Tienda Plus con catálogo dinámico...")
    print("📍 Servidor: PC\\SQLEXPRESS")
    print("🛍️  Sistema: Catálogo dinámico + Panel de administración")
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)