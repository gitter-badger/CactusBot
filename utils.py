def request(parent, req, url, **kwargs):
    """Send HTTP request to Beam."""

    if req.lower() in ('get', 'head', 'post', 'put', 'delete', 'options'):
        response = parent.session.__getattribute__(req.lower())(
            path + url, data=**kwargs
        )

        if 'error' in response.json().keys():
            parent.logger.warn("Error: {}".format(response.json()['error']))

        return response.json()
    else:
        parent.logger.debug("Invalid request: {}".format(req))
        raise BadSessionTypeException(req.lower)
