@app.route('/event')
def event():
    search_query = request.args.get('search', '').lower()
    search_month = request.args.get('search_month')
    page = request.args.get('page', 1, type=int)
    events_per_page = 9
    events_by_month_year = {}
    preferred_width = 1920
    search_date_parsed = None

    if search_month:
        try:
            search_date_parsed = datetime.strptime(search_month, '%Y-%m')
        except ValueError:
            search_date_parsed = None

    # Base MongoDB query
    filters = {}
    if search_query:
        filters["event_name"] = {"$regex": search_query, "$options": "i"}
    if search_date_parsed:
        filters["event_date"] = {
            "$gte": search_date_parsed,
            "$lte": search_date_parsed.replace(day=calendar.monthrange(search_date_parsed.year, search_date_parsed.month)[1])
        }

    base_query = mongo.db.events.find(filters).sort("event_date", 1)

    # Pagination
    total_events = base_query.count()
    paginated_events = base_query.skip((page - 1) * events_per_page).limit(events_per_page)

    # Process events for grouping and preferred images
    for event in paginated_events:
        event_images = mongo.db.images.find({"event_id": ObjectId(event["_id"])})
        preferred_image = None
        if event_images.count() > 0:
            preferred_image = min(event_images, key=lambda img: abs(img["width"] - preferred_width))
        
        event["preferred_image"] = preferred_image
        month_year = f"{calendar.month_name[event['event_date'].month]} {event['event_date'].year}"

        if month_year not in events_by_month_year:
            events_by_month_year[month_year] = []
        events_by_month_year[month_year].append(event)

    # Sort month-year keys
    sorted_month_years = sorted(
        events_by_month_year.keys(),
        key=lambda x: (int(x.split(' ')[1]), -1 if int(x.split(' ')[1]) == datetime.now().year else 0)
    )

    return render_template(
        'event.html',
        events_by_month_year={key: events_by_month_year[key] for key in sorted_month_years},
        search_query=search_query,
        search_month=search_month,
        current_page=page,
        total_pages=(total_events + events_per_page - 1) // events_per_page
    )


@app.route('/ticket/<event_id>')
def ticket(event_id):
    error_message = None
    preferred_width = 1920

    # Get user info from session
    user_id = session.get('user_id')
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    # Get the event by ID
    event = mongo.db.events.find_one({"_id": ObjectId(event_id)})
    if not event:
        return redirect(url_for('landing'))  # Redirect if event not found

    # Determine ticket availability
    ticket_categories = mongo.db.ticket_categories.find({"event_id": ObjectId(event_id)})
    tickets_available = any(
        category["seats_available"] > mongo.db.tickets.count_documents({"category_id": ObjectId(category["_id"])})
        for category in ticket_categories
    )

    # Get preferred image for the event
    event_images = mongo.db.images.find({"event_id": ObjectId(event_id)})
    preferred_image = None
    if event_images.count() > 0:
        preferred_image = min(event_images, key=lambda img: abs(img["width"] - preferred_width))

    # Prepare event image information
    event_image = {
        "ImageURL": preferred_image["url"] if preferred_image else url_for('static', filename='images/default.jpg')
    }

    return render_template(
        'ticket.html',
        event=event,
        event_image=event_image,
        user=user,
        tickets_available=tickets_available
    )
