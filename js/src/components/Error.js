import React from 'react'

const Error = ({error}) => {
  console.error('Error:', error)
  return (
    <div>
      <h3>Error:</h3>
      <p>{error}</p>
    </div>
  )
}

export default Error
