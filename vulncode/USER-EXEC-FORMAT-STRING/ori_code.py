def execute_code(request):
    if request.method == 'POST':
        user_name = request.POST.get('first_name', '')
        mapped_input = list(map(exec, [f"setname('{user_name}')"]))

