from django.shortcuts import render, redirect
from django.db import connection, transaction
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from datetime import date
from django.contrib.auth import authenticate, login, logout
import crcmod

def home_view(request):
    return render(request, 'home.html')

def menu_view(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT ProductID, ProductName, Price FROM dbo.Products")
        products = cursor.fetchall()
    cart = request.session.get('cart', {})
    total_items = sum(cart.values())
    return render(request, 'menu.html', {
        'products': products, 
        'total_items': total_items 
    })

def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    request.session['cart'] = cart
    if request.GET.get('next') == 'cart':
        return redirect('cart')
    return redirect('menu')

def login_view(request):
    return render(request, 'login.html')

def orders_view(request):
    with connection.cursor() as cursor:
        query = """
            SELECT 
                o.OrderID, 
                o.OrderDate, 
                c.Cusname, 
                p.ProductName, 
                od.Quantity, 
                od.Price
            FROM dbo.Orders o
            INNER JOIN dbo.Customers c ON o.CusID = c.CusID
            INNER JOIN dbo.Orderdetails od ON o.OrderID = od.OrderID
            INNER JOIN dbo.Products p ON od.ProductID = p.ProductID
            ORDER BY o.OrderDate DESC
        """
        cursor.execute(query)
        orders = cursor.fetchall()
    
    return render(request, 'orders.html', {'orders': orders})

def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    subtotal = 0
    
    with connection.cursor() as cursor:
        for product_id, quantity in cart.items():
            cursor.execute("SELECT ProductID, ProductName, Price FROM dbo.Products WHERE ProductID = %s", [product_id])
            product = cursor.fetchone()
            if product:
                item_total = product[2] * quantity
                subtotal += item_total
                cart_items.append({
                    'id': product[0],
                    'product_name': product[1],
                    'price': product[2],
                    'quantity': quantity,
                    'total': item_total
                })
    
    tax = round(subtotal * Decimal('0.07'), 2)
    total_all = subtotal + tax
    return render(request, 'cart.html', {
        'cart_items': cart_items, 
        'subtotal': subtotal, 
        'tax': tax, 
        'total_all': total_all
    })
    subtotal = sum(item['total'] for item in cart_items)
    tax = round(subtotal * 0.07, 2)
    total_all = subtotal + tax
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'total_all': total_all
    }
    return render(request, 'cart.html', context)

def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    if product_id_str in cart:
        del cart[product_id_str]
    request.session['cart'] = cart
    return redirect('cart')
    


def decrease_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    if product_id_str in cart:
        if cart[product_id_str] > 1:
            cart[product_id_str] -= 1
        else:
            del cart[product_id_str]
    request.session['cart'] = cart
    return redirect('cart')


def checkout(request):
    cart = request.session.get('cart', {})
    total_price = 0
    
    with connection.cursor() as cursor:
        for product_id, quantity in cart.items():
            cursor.execute("SELECT Price FROM dbo.Products WHERE ProductID = %s", [product_id])
            row = cursor.fetchone()
            if row:
                total_price += float(row[0]) * quantity
                
    pp_payload = generate_promptpay_code("0645138205", total_price) 

    return render(request, 'checkout.html', {
        'total_price': total_price,
        'pp_payload': pp_payload
    })

def complete_order(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        if not cart:
            return redirect('menu')

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    
                    cursor.execute("SELECT COUNT(*) FROM dbo.Orders")
                    order_count = cursor.fetchone()[0]
                    next_cus_id = order_count + 1 

                    
                    total_price = 0
                    for product_id, quantity in cart.items():
                        cursor.execute("SELECT Price FROM dbo.Products WHERE ProductID = %s", [product_id])
                        row = cursor.fetchone()
                        if row:
                            total_price += float(row[0]) * int(quantity)

                    
                    cursor.execute("""
                        INSERT INTO dbo.Orders (OrderDate, Totalamount, CusID, EmpID) 
                        OUTPUT INSERTED.OrderID
                        VALUES (GETDATE(), %s, %s, 1) 
                    """, [total_price, next_cus_id])
                    
                    order_id = cursor.fetchone()[0]

                    
                    for product_id, quantity in cart.items():
                        cursor.execute("SELECT Price FROM dbo.Products WHERE ProductID = %s", [product_id])
                        product_price = cursor.fetchone()[0]
                        
                        
                        cursor.execute("""
                            INSERT INTO dbo.Orderdetails (OrderID, ProductID, Quantity, Price)
                            VALUES (%s, %s, %s, %s)
                        """, [order_id, product_id, quantity, product_price])

                        
                        cursor.execute("""
                            UPDATE dbo.Products 
                            SET StockQuantity = StockQuantity - %s 
                            WHERE ProductID = %s
                        """, [quantity, product_id])

            del request.session['cart']
            return render(request, 'success.html')

        except Exception as e:
            print(f"Error: {e}")
            return render(request, 'checkout.html', {'error': 'บันทึกข้อมูลไม่สำเร็จ'})

    return redirect('menu')

def generate_promptpay_code(mobile_id, amount):

    field_00 = "000201"
    field_01 = "010211"
    
    
    merchant_info = "0066" + mobile_id[1:]
    field_29 = f"0010A0000006770101110113{merchant_info}"
    field_29 = f"29{len(field_29):02d}{field_29}"
    
    field_53 = "5303764"
    
    formatted_amount = "{:.2f}".format(float(amount))
    field_54 = f"54{len(formatted_amount):02d}{formatted_amount}"
    
    field_58 = "5802TH"
    field_63 = "6304"
    
    payload = field_00 + field_01 + field_29 + field_53 + field_54 + field_58 + field_63
    
    import crcmod
    crc16 = crcmod.predefined.Crc('crc-16-mcrf4xx')
    crc16.update(payload.encode('utf-8'))
    crc_result = hex(crc16.crcValue).upper()[2:].zfill(4)
    
    return payload + crc_result

@login_required
def daily_report(request):
    with connection.cursor() as cursor:
        
        cursor.execute("""
            SELECT SUM(Totalamount) 
            FROM dbo.Orders 
            WHERE CAST(OrderDate AS DATE) = %s
        """, [date.today()])
        daily_total = cursor.fetchone()[0] or 0
        
    return render(request, 'daily_report.html', {'daily_total': daily_total})

def login_view(request):
    
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        user_in = request.POST.get('username')
        pass_in = request.POST.get('password')
        
        user = authenticate(request, username=user_in, password=pass_in)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            
            return render(request, 'login.html', {'error': 'ID หรือรหัสผ่านไม่ถูกต้อง'})
            
    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    with connection.cursor() as cursor:
        
        cursor.execute("SELECT SUM(Totalamount) FROM dbo.Orders")
        total_sales = cursor.fetchone()[0] or 0
        
        
        cursor.execute("SELECT SUM(Totalamount) FROM dbo.Orders WHERE CAST(OrderDate AS DATE) = CAST(GETDATE() AS DATE)")
        daily_sales = cursor.fetchone()[0] or 0
        
        
        cursor.execute("SELECT COUNT(*) FROM dbo.Orders")
        total_orders = cursor.fetchone()[0] or 0
        
        
        cursor.execute("SELECT OrderID, OrderDate, CusID, Totalamount FROM dbo.Orders ORDER BY OrderID DESC")
        all_orders = cursor.fetchall()
        
    return render(request, 'dashboard.html', {
        'total_sales': total_sales,
        'daily_sales': daily_sales,
        'total_orders': total_orders,
        'all_orders': all_orders
    })

def logout_view(request):
    logout(request) 
    return redirect('login')

@login_required(login_url='login')
def sales_history_view(request):
    with connection.cursor() as cursor:
        sql = """
            SELECT 
                o.OrderID AS id, 
                o.OrderDate AS date, 
                ISNULL(STRING_AGG(CAST(p.Productname AS NVARCHAR(MAX)), ', '), '-') AS product_list,
                ISNULL(c.Cusname, 'ทั่วไป') AS customer_name, 
                o.Totalamount AS total_money
            FROM dbo.Orders o
            LEFT JOIN dbo.Orderdetails d ON o.OrderID = d.OrderID
            LEFT JOIN dbo.Products p ON d.ProductID = p.ProductID
            LEFT JOIN dbo.customers c ON o.CusID = c.CusID
            -- แก้จุดนี้: ใส่คอลัมน์ที่ "ไม่ได้อยู่ใน STRING_AGG" ให้ครบ
            GROUP BY o.OrderID, o.OrderDate, o.Totalamount, c.Cusname
            ORDER BY o.OrderDate DESC
        """
        cursor.execute(sql)
        
        all_orders = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
    return render(request, 'sales_history.html', {'all_orders': all_orders})
