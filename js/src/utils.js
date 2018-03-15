export const load_script = url => {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = url
    script.onload = () => resolve()
    script.onreadystatechange = () => resolve()
    script.onerror = () => reject()
    document.body.appendChild(script)
  })
}

export const make_url = path => {
  let root = process.env.REACT_APP_ROOT_URL
  if (root.startsWith('/')) {
    root = window.location.origin + root
  }
  return root + path
}

export const request = (path, send_data, method, expected_statuses) => {
  const url = make_url(path)

  if (Number.isInteger(expected_statuses)) {
    expected_statuses = [expected_statuses]
  } else {
    expected_statuses = expected_statuses || [200]
  }
  if (send_data) {
    send_data = JSON.stringify(send_data)
  }
  // await sleep(2000)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const on_error = msg => {
      console.error('request error', msg, url, xhr)
      reject(msg)
    }
    xhr.open(method || 'GET', url)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.onload = () => {
      if (expected_statuses.includes(xhr.status)) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch (error) {
          on_error(`error decoding json: ${error}`)
          return
        }
      } else {
        on_error(`wrong response code ${xhr.status}, Response: ${xhr.responseText.substr(0, 500)}`)
      }
    }
    xhr.onerror = () => on_error(`Error requesting data ${xhr.statusText}: ${xhr.status}`)
    xhr.send(send_data)
  })
}
