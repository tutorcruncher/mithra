import React, { Component } from 'react'
import {format_ts} from '../utils'
import Error from './Error'

class ListView extends Component {
  constructor (props) {
    super(props)
    this.state = {
      items: [],
      error: null,
    }
    this.title = null
    this.ItemComponent = null
    this.url = null
  }

  async componentDidMount () {
    this.props.setRootState({nav_title: this.title, status: 'loading'})
    try {
      const data = await this.props.requests.get(this.url)
      this.setState({items: data.items})
      this.props.setRootState({status: 'ok'})
    } catch (err) {
      this.setState({error: err})
    }
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    }
    return (
      <ul className="list-group py-3 mx-0">
        {this.state.items.map((item, i) => (
          <li key={i} className="list-group-item">
            <this.ItemComponent item={item}/>
          </li>
        ))}
      </ul>
    )
  }
}

const Person = ({item}) => (
  <div className="d-flex justify-content-between">
    <div>
      <h6 className="my-0">{item.name}</h6>
      <pre className="mb-0 mt-1">
        <code>{JSON.stringify(item, null, 2)}</code>
      </pre>
    </div>
    <span className="float-right text-muted">{format_ts(item.last_seen)}</span>
  </div>
)

export class People extends ListView {
  constructor (props) {
    super(props)
    this.title = 'People'
    this.ItemComponent = Person
    this.url = '/people/'
  }
}

const Company = ({item}) => (
  <div className="d-flex justify-content-between">
    <div>
      <h6 className="my-0">{item.name}</h6>
      <pre className="mb-0 mt-1">
        <code>{JSON.stringify(item, null, 2)}</code>
      </pre>
    </div>
    <span className="float-right text-muted">{format_ts(item.created)}</span>
  </div>
)

export class Companies extends ListView {
  constructor (props) {
    super(props)
    this.title = 'Companies'
    this.ItemComponent = Company
    this.url = '/companies/'
  }
}
