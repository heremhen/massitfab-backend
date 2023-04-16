# Third party libraries
import os
from datetime import datetime
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage
import math

# Local Imports
from massitfab.settings import connectDB, disconnectDB, verifyToken, log_error, json
from .serializers import CreateProductSerializer, CreateReviewSerializer, UpdateProductSerializer, UpdateProfileSerializer, AddToWishlistSerializer


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_profile(request, username):
    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        # Check if user does not exists while also retrieving the information
        cur.execute(
            "SELECT id, username, summary, profile_picture, created_at FROM fab_user WHERE username = %s",
            [username]
        )
        result = cur.fetchone()

        if result is None:
            log_error('get_profile', json.dumps(
                {"username": username}), 'User does not exist')
            return Response(
                {'message': 'User does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get the page number and page size from the query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        # Calculate the offset based on the page number and page size
        offset = (page - 1) * page_size

        # Query the related products with pagination
        cur.execute(
            """SELECT id, title, description, st_price, created_at FROM product
               WHERE fab_user_id = %s
               ORDER BY created_at DESC
               LIMIT %s OFFSET %s""",
            [result[0], page_size, offset]
        )
        results = cur.fetchall()

        # Convert the result rows to a list of dictionaries
        products = []
        for row in results:
            products.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'st_price': float(row[3]),
                'created_at': row[4].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            })

        # Get the total count of related products
        cur.execute(
            "SELECT COUNT(*) FROM product WHERE fab_user_id = %s",
            [result[0]]
        )
        total_count = cur.fetchone()[0]  # type: ignore

        # Calculate the number of pages based on the total count and page size
        num_pages = math.ceil(total_count / page_size)

        resp = {
            "data": {
                'username': result[1],
                'summary': result[2],
                'profile_picture': result[3],
                'created_at': result[4].strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'related_products': products,
                'list': {
                    'page': page,
                    'page_size': page_size,
                    'num_pages': num_pages,
                    'total_count': total_count
                }
            },
            "message": "Амжилттай!"
        }
        return Response(
            resp,
            status=status.HTTP_200_OK
        )
    except Exception as error:
        log_error('get_profile', json.dumps(
            {"username": username}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(["PUT"])
def update_profile(request):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    serializer = UpdateProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    conn = None
    fab_id = auth.get('user_id')
    try:
        conn = connectDB()
        cur = conn.cursor()

        cur.execute(
            'SELECT username, summary, profile_picture FROM fab_user WHERE id=%s', [fab_id])
        result = cur.fetchone()

        if result is None:
            return Response(
                {'message': 'You are not authorized to update this profile!'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get the old profile picture from the database
        cur.execute(
            "SELECT profile_picture FROM fab_user WHERE id=%s", [fab_id])
        oldpro = str(cur.fetchone()[0])  # type: ignore
        pro = data.get('profile_picture')  # type: ignore
        profile_picture = None

        # Check if the request is valid
        if pro:
            file_path = os.path.join(settings.MEDIA_ROOT, 'public', 'img')
            storage = FileSystemStorage(location=file_path)

            # Remove the old profile picture from local storage
            if oldpro != 'public/img/sandy.png':
                full_path = os.path.join(settings.MEDIA_ROOT, oldpro)
                if os.path.isfile(full_path):
                    os.remove(full_path)
            filename = storage.save(pro.name, pro)
            profile_picture = os.path.join(
                file_path, filename).replace('\\', '/')

        # Add the local path into the database
        values = (data.get('username'), data.get('summary') if data.get('summary')  # type: ignore
                  else None, profile_picture, fab_id)  # type: ignore
        cur.execute(
            "UPDATE fab_user SET username=%s, summary=%s, profile_picture=%s WHERE id=%s", values)
        conn.commit()

        data = {
            'message': 'Амжилттай шинэчлэгдсэн!'
        }
        return Response(
            data,
            status=status.HTTP_202_ACCEPTED
        )

    except Exception as error:
        log_error('update_profile', json.dumps(
            {"user_id": fab_id, "data": data}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_products(request):  # Recently uploaded products
    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        # Get pagination parameters from query string
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        offset = (page - 1) * page_size

        # Get total number of products
        cur.execute("SELECT COUNT(*) FROM product")
        total_count = cur.fetchone()[0]  # type: ignore

        # Get paginated products data
        cur.execute("""
            SELECT id, title, description, subcategory_id, st_price, created_at
            FROM product
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, [page_size, offset])
        rows = cur.fetchall()

        # Serialize product data
        products = []
        for row in rows:
            product = {
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'subcategory_id': row[3],
                'st_price': float(row[4]),
                'created_at': row[5].strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            }
            products.append(product)

        # Build response dictionary with pagination information
        resp = {
            'data': products,
            'pagination': {
                'total_count': total_count,
                'page_count': math.ceil(total_count / page_size),
                'page': page,
                'page_size': page_size,
            },
            'message': 'Амжилттай!',
        }
        return Response(resp, status=status.HTTP_200_OK)
    except Exception as error:
        log_error('get_products', json.dumps({}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_product_details(request, id):
    conn = None
    try:
        con = connectDB()
        cur = con.cursor()
        cur.execute(
            """SELECT title, description, schedule, fab_user_id, start_date, end_date, subcategory_id, hashtags, st_price, 
                created_at, updated_at, is_removed FROM product WHERE id=%s;""", [id])
        result = cur.fetchone()

        if result is None or result[-1] != False:
            log_error('get_product', json.dumps({'product_id': id}),
                      'This product is removed or does not exist')
            return Response(
                {'message': 'Product does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        cur.execute("SELECT resource FROM gallery WHERE product_id = %s", [id])
        medias = cur.fetchall()
        flat_gallery = [item for sublist in medias for item in sublist]

        cur.execute("SELECT source FROM route WHERE product_id = %s", [id])
        links = cur.fetchall()
        flat_link = [item for sublist in links for item in sublist]

        resp = {
            "data": {
                "id": id,
                "title": result[0],
                "description": result[1],
                "schedule": result[2],
                "owner": result[3],
                "start_date": result[4],
                "end_date": result[5],
                "categories": result[6],
                "hashtags": result[7],
                "price": result[8],
                "published": result[9],
                "edited": result[10],
                "gallery": flat_gallery,
                "link": flat_link
            },
            "message": "Амжилттай!",
        }
        return Response(
            resp,
            status=status.HTTP_200_OK
        )
    except Exception as error:
        log_error('get_product', "{}", str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['POST'])
def create_product(request):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    serializer = CreateProductSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        # Use the connection's autocommit attribute to ensure all queries
        # are part of the same transaction
        conn.autocommit = False

        # Start a new transaction
        cur.execute("BEGIN")

        # content_data = data.get('content')  # type: ignore
        # schedule = datetime.strptime(content_data.get('schedule'), '%Y-%m-%d %H:%M:%S.%f') if content_data.get('schedule') else None
        # start_date = datetime.strptime(content_data.get('start_date'), '%Y-%m-%d %H:%M:%S.%f') if content_data.get('start_date') else None
        # end_date = datetime.strptime(content_data.get('end_date'), '%Y-%m-%d %H:%M:%S.%f') if content_data.get('end_date') else None
        # opening = (
        #     content_data.get('title'),
        #     content_data.get('description'),
        # )
        # ending = (
        #     content_data.get('subcategory_id'),
        #     content_data.get('hashtags') if content_data.get('hashtags') else '',
        #     float(content_data.get('st_price')) if content_data.get('st_price') else 0,
        # )
        # if schedule is not None:
        #     cur.execute(
        #         """INSERT INTO product
        #             VALUES (DEFAULT, %s, %s, CAST(%s AS timestamp without time zone), %s, CAST(%s AS timestamp without time zone), CAST(%s AS timestamp without time zone), %s, %s, %s, DEFAULT, DEFAULT, %s) RETURNING id""",
        #         (*opening, schedule, auth.get('user_id'),
        #          start_date, end_date, *ending, None)
        #     )
        # else:
        #     cur.execute(
        #         """INSERT INTO product
        #             VALUES (DEFAULT, %s, %s, DEFAULT, %s, CAST(%s AS timestamp without time zone), CAST(%s AS timestamp without time zone), %s, %s, %s, DEFAULT, DEFAULT, %s) RETURNING id""",
        #         (*opening, auth.get('user_id'),
        #          start_date, end_date, *ending, None)
        #     )

        # Execute an query using parameters
        values = (
            data.get('title'),  # type: ignore
            data.get('description'),  # type: ignore
            auth.get('user_id'),
            int(data.get('subcategory_id')),  # type: ignore
            float(data.get('st_price', 0))  # type: ignore
        )
        cur.execute("""INSERT INTO product(title, description, fab_user_id, subcategory_id, st_price)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id;""", values)
        content_id = cur.fetchone()[0]  # type: ignore

        sources = data.get('source')        # type: ignore
        if sources:
            sauces = sources.split("&")
            for source in sauces:
                values = (source, content_id)
                cur.execute(
                    """INSERT INTO route(source, product_id) 
                        VALUES (%s, %s)""",
                    values
                )

        # Set the upload folder to the public/img directory
        file_path = os.path.join(settings.MEDIA_ROOT, 'public', 'img')
        gallery_data = data.get('resource')  # type: ignore
        if gallery_data:
            storage = FileSystemStorage(location=file_path)
            filenames = []
            for image_file in gallery_data:
                filename = storage.save(image_file.name, image_file)
                filenames.append(filename)
                values = (os.path.join(file_path, filename).replace(
                    '\\', '/'), content_id)
                cur.execute(
                    """INSERT INTO gallery (resource, product_id)
                        VALUES (%s, %s)""",
                    values
                )

        # Commit the changes to the database
        conn.commit()

        data = {
            'message': 'Байршуулалт амжилттай!'
        }
        return Response(
            data,
            status=status.HTTP_201_CREATED
        )

    except Exception as error:
        log_error('create_product', json.dumps(
            {"user_id": auth.get('user_id'), "data": data}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['PUT'])
def update_product(request, id):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    serializer = UpdateProductSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        values = (id, auth.get('user_id'))
        cur.execute(
            'SELECT id, fab_user_id FROM product WHERE id = %s AND fab_user_id = %s', values)
        content_id, uid = cur.fetchone() or (None, None)  # type: ignore

        if content_id is None:
            return Response(
                {'message': 'You are not authorized to edit this product!'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Update the product data
        values = []
        query = "UPDATE product SET updated_at=now()"
        title = data.get('title')  # type: ignore
        description = data.get('description')  # type: ignore
        subcategory_id = data.get('subcategory_id')  # type: ignore
        st_price = data.get('st_price')  # type: ignore
        if title:
            query += ", title=%s"
            values.append(title)
        if description:
            query += ", description=%s"
            values.append(description)
        if subcategory_id:
            query += ", subcategory_id=%s"
            values.append(int(subcategory_id))
        if st_price:
            query += ", st_price=%s"
            values.append(float(st_price))
        query += " WHERE id=%s"
        values.append(id)
        cur.execute(query, values)

        # Delete deleted gallery files and rows from the database
        resource_deleted = data.get('resource_deleted')  # type: ignore
        if resource_deleted:
            res_list = resource_deleted.split('&')
            for deleted in res_list:
                # Delete the file from the Django media directory
                full_path = os.path.join(settings.MEDIA_ROOT, deleted)
                if os.path.isfile(full_path):
                    os.remove(full_path)
                values = (deleted, id)
                cur.execute(
                    "DELETE FROM gallery WHERE resource = %s AND product_id = %s", values
                )

        # Delete deleted source files and rows from the database
        source_deleted = data.get('source_deleted')  # type: ignore
        if source_deleted:
            src_list = source_deleted.split('&')
            for deleted in src_list:
                # Delete the file from the Django media directory
                full_path = os.path.join(settings.MEDIA_ROOT, deleted)
                if os.path.isfile(full_path):
                    os.remove(full_path)
                values = (deleted, id)
                cur.execute(
                    "DELETE FROM route WHERE source = %s AND product_id = %s", values
                )

        # Insert new source files into the database
        sources = data.get('source')  # type: ignore
        if sources:
            srcs = sources.split('&')
            for source in srcs:
                values = (source, content_id)
                cur.execute(
                    "INSERT INTO route(source, product_id) VALUES (%s, %s)",
                    values
                )

        # Insert new gallery files into the database
        file_path = os.path.join(settings.MEDIA_ROOT, 'public', 'img')
        gallery_data = data.get('resource')  # type: ignore
        if gallery_data:
            storage = FileSystemStorage(location=file_path)
            filenames = []
            for image_file in gallery_data:
                filename = storage.save(image_file.name, image_file)
                filenames.append(filename)
                values = (os.path.join(file_path, filename).replace(
                    '\\', '/'), content_id)
                cur.execute(
                    """INSERT INTO gallery (resource, product_id)
                        VALUES (%s, %s)""",
                    values
                )

        # Commit the changes to the database
        conn.commit()

        data = {
            'message': 'Амжилттай шинэчлэгдлээ!'
        }
        return Response(
            data,
            status=status.HTTP_202_ACCEPTED
        )

    except Exception as error:
        log_error('update_product', json.dumps(
            {"user_id": auth.get("user_id"), "data": data}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['DELETE'])
def delete_product(request, id):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )

    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        values = (id, auth.get('user_id'))
        cur.execute(
            'SELECT id, fab_user_id FROM product WHERE id = %s AND fab_user_id = %s', values)
        row = cur.fetchone()

        if row is None:
            return Response(
                {'message': 'You are not authorized to edit this product!'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        cur.execute(
            'UPDATE product SET is_removed = True WHERE id = %s AND fab_user_id = %s', values)

        # Commit the changes to the database
        conn.commit()

        data = {
            'message': 'Амжилттай устгагдлаа!'
        }
        return Response(
            data,
            status=status.HTTP_201_CREATED
        )

    except Exception as error:
        log_error('delete_product', json.dumps({"user_id": auth.get(
            'user_id'), "data": request.data, "product_id": id}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def search_products(request):
    keyword = str(request.GET.get('keyword', ''))
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))

    conn = None
    try:
        conn = connectDB()
        cur = conn.cursor()

        # get the total number of matching products
        cur.execute(
            "SELECT COUNT(*) FROM product WHERE title ILIKE %s", ['%'+keyword+'%'])
        total_count = cur.fetchone()[0]  # type: ignore

        # get a list of products matching the keyword, paginated
        cur.execute(
            "SELECT id, title, description, fab_user_id, st_price, created_at "
            "FROM product "
            "WHERE is_removed = false AND title ILIKE %s "
            "ORDER BY created_at DESC "
            "LIMIT %s OFFSET %s",
            ['%'+keyword+'%', limit, (page-1)*limit]
        )
        rows = cur.fetchall()

        products = []
        for row in rows:
            products.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'creator': row[3],
                'price': row[4],
                'created_at': row[5].strftime('%Y-%m-%dT%H:%M:%S')
            })
        print('resp')
        resp = {
            'data': {
                'products': products,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total_count': total_count,
                    'total_pages': math.ceil(total_count / limit)
                }
            },
            'message': 'Амжилттай!'
        }

        return Response(resp, status=status.HTTP_200_OK)
    except Exception as error:
        log_error('search_product', json.dumps(
            {"keyword": keyword, "page": page, "limit": limit}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['POST'])
# User should not be able to add it's own products to this list
def add_to_wishlist(request):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    serializer = AddToWishlistSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    product_id = int(data.get('product_id'))  # type: ignore
    user_id = auth.get('user_id')

    conn = None
    try:
        conn = connectDB()
        cur = conn.cursor()

        # Check if product exists
        cur.execute(
            "SELECT id FROM product WHERE id = %s",
            [product_id]
        )
        result = cur.fetchone()
        if result is None:
            log_error('add_to_wishlist', json.dumps(
                {"message": 'Энэхүү бүтээгдэхүүн нь систэмд бүртгэлгүй байна.', "data": data}), 'error. result is none')
            return Response({'message': 'Энэхүү бүтээгдэхүүн нь систэмд бүртгэлгүй байна.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if product is already in wishlist
        cur.execute(
            "SELECT id FROM wishlist WHERE fab_user_id = %s AND product_id = %s",
            [user_id, product_id]
        )
        result = cur.fetchone()
        if result is not None:
            cur.execute("DELETE FROM wishlist WHERE id=%s", [result])
            conn.commit()
            return Response({'message': 'Хүслийн жагсаалтнаас амжилттай хасагдлаа!'}, status=status.HTTP_200_OK)

        # Add product to wishlist
        cur.execute(
            "INSERT INTO wishlist (fab_user_id, product_id) VALUES (%s, %s) RETURNING id",
            [user_id, product_id]
        )
        wishlist_id = cur.fetchone()[0]  # type: ignore
        conn.commit()

        return Response({'message': 'Хүслийн жагсаалтад амжилттай бүртгэгдлээ!', 'wishlist_id': wishlist_id}, status=status.HTTP_201_CREATED)
    except Exception as e:
        log_error('add_to_wishlist', json.dumps({"data": data}), str(e))
        return Response({'message': 'Unable to add product to wishlist'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['GET'])
def get_wishlist(request):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    print('wtf')
    user_id = auth.get('user_id')
    page_size = request.query_params.get('page_size', 10)
    page_number = request.query_params.get('page_number', 1)

    conn = None
    try:
        conn = connectDB()
        cur = conn.cursor()

        # Get count of total wishlist items
        cur.execute(
            "SELECT COUNT(*) FROM wishlist WHERE fab_user_id = %s",
            [user_id]
        )
        total_items = cur.fetchone()[0]  # type: ignore

        # Calculate offset and limit for pagination
        offset = (page_number - 1) * page_size
        limit = page_size

        # Get wishlist items for the requested page
        cur.execute(
            "SELECT product.id, product.title, product.st_price FROM product JOIN wishlist ON wishlist.product_id = product.id WHERE wishlist.fab_user_id = %s ORDER BY wishlist.created_at DESC OFFSET %s LIMIT %s",
            [user_id, offset, limit]
        )
        wishlist_items = []
        for row in cur.fetchall():
            wishlist_items.append({
                'id': row[0],
                'title': row[1],
                'st_price': row[2],
            })

        # Build response
        resp = {
            'data': wishlist_items,
            'total_items': total_items,
            'page_size': page_size,
            'page_number': page_number,
            'message': 'Амжилттай!',
        }

        return Response(resp, status=status.HTTP_200_OK)
    except Exception as e:
        log_error('get_wishlist', json.dumps(
            {"user_id": user_id, "data": request.data}), str(e))
        return Response({'message': 'Хүслийн жагсаалт руу хандаж чадсангүй!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['POST'])
def create_review(request, product_id):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    serializer = CreateReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user_id = auth.get('user_id')  # type: ignore

    conn = None
    try:
        conn = connectDB()
        cur = conn.cursor()

        # check if the product exists
        cur.execute(
            "SELECT id FROM product WHERE id = %s", [product_id]
        )
        result = cur.fetchone()

        if result is None:
            log_error('create_review', json.dumps(
                {"product_id": product_id}), 'Product does not exist')
            return Response(
                {'message': 'Product does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # insert review into the database
        cur.execute(
            "INSERT INTO review (score, comment, fab_user_id, product_id) VALUES (%s, %s, %s, %s) RETURNING id",
            [int(data.get('score')), data.get('comment', None),
             user_id, product_id]  # type: ignore
        )
        review_id = cur.fetchone()[0]   # type: ignore
        conn.commit()

        resp = {
            "data": {
                "id": review_id,
                "score": data.get('score'),  # type: ignore
                "comment": data.get('comment', None),  # type: ignore
                "fab_user_id": user_id,
                "product_id": product_id,
                "created_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            },
            "message": "Амжилттай!"
        }
        return Response(
            resp,
            status=status.HTTP_201_CREATED
        )
    except Exception as error:
        log_error('create_review', json.dumps(
            {"product_id": product_id}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг хийхэд алдаа гарлаа.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_reviews(request, product_id):
    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        # get pagination parameters from request
        limit = int(request.GET.get('limit', 20))
        cursor = int(request.GET.get('cursor', 0))

        # retrieve reviews using cursor-based pagination
        cur.execute(
            """SELECT id, score, comment, fab_user_id, created_at FROM review WHERE product_id=%s AND id > %s ORDER BY id LIMIT %s""",
            [product_id, cursor, limit]
        )
        rows = cur.fetchall()

        # construct response data
        reviews = []
        for row in rows:
            review = {
                'id': row[0],
                'score': row[1],
                'comment': row[2],
                'user_id': row[3],
                'created_at': row[4].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
            reviews.append(review)

        # construct response with pagination information
        resp = {
            "data": reviews,
            "pagination": {
                "has_next": bool(rows),
                "cursor": rows[-1][0] if rows else None
            },
            "message": "Success"
        }

        return Response(resp, status=status.HTTP_200_OK)
    except Exception as error:
        log_error('get_reviews', json.dumps(
            {"product_id": product_id}), str(error))
        return Response({'message': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['DELETE'])
def delete_review(request, review_id):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )

    conn = None
    try:
        # establish database connection
        conn = connectDB()
        cur = conn.cursor()

        # Check if review exists
        cur.execute(
            "SELECT fab_user_id FROM review WHERE id = %s", [review_id]
        )
        result = cur.fetchone()

        if result is None:
            log_error('delete_review', "{}", 'Review does not exist')
            return Response(
                {'message': 'Review does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is authorized to delete the review
        user_id = auth.get('user_id')
        if user_id != result[0]:
            log_error('delete_review', "{}", 'Unauthorized')
            return Response(
                {'message': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Delete the review
        cur.execute(
            "DELETE FROM review WHERE id = %s", [review_id]
        )
        conn.commit()

        resp = {
            "message": "Амжилттай устгалаа!"
        }
        return Response(
            resp,
            status=status.HTTP_200_OK
        )

    except Exception as error:
        log_error('delete_review', json.dumps(
            {"review_id": review_id}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['POST'])
def add_product_to_cart(request, product_id):
    auth_header = request.headers.get('Authorization')
    auth = verifyToken(auth_header)
    if(auth.get('status') != 200):
        return Response(
            {'message': auth.get('error')},
            status=status.HTTP_401_UNAUTHORIZED
        )
    user_id = auth.get('user_id')

    conn = None
    try:
        conn = connectDB()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO customer (fab_user_id, product_id)
            VALUES (%s, %s)
            RETURNING id
            """,
            (user_id, product_id)
        )
        cart_id = cur.fetchone()[0]  # type: ignore
        conn.commit()

        resp = {
            "cart_id": cart_id,
            "user_id": user_id,
            "product_id": product_id,
            "message": "Сагсанд амжилттай нэмэгдлээ!",
        }
        return Response(
            resp,
            status=status.HTTP_200_OK
        )
    except Exception as error:
        log_error('delete_review', json.dumps(
            {"product_id": product_id, "user_id": user_id}), str(error))
        return Response(
            {'message': 'Уучлаарай, үйлдлийг гүйцэтгэхэд алдаа гарлаа.', },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if conn is not None:
            disconnectDB(conn)


@api_view(['POST'])
def checkout_cart(request):
    pass


@api_view(['DELETE'])
def remove_from_cart(request, product_id):
    pass
