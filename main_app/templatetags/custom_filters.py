from django import template

register = template.Library()


@register.filter
def join(value, arg):
    return arg.join([str(item) for item in value])

@register.filter(name='chunk')
def chunk_list(list_data, chunk_size):
    """
    Divide una lista en trozos (chunks) de un tamaño específico.
    Ejemplo: {{ my_list|chunk:4 }}
    """
    chunked_list = []
    for i in range(0, len(list_data), chunk_size):
        chunked_list.append(list_data[i:i + chunk_size])
    return chunked_list
