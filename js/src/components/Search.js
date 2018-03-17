import React, { Component } from 'react'
import {Link} from 'react-router-dom'
import {format_ts} from '../utils'
import Error from './Error'

class Search extends Component {
  constructor (props) {
    super(props)
    this.state = {
      items: [],
      query: this.props.query,
      loaded: false,
      error: null,
    }
    this.get = this.get.bind(this)
    this.mounted = false
  }

  async componentDidMount () {
    this.mounted = true
    this.props.setRootState({page_title: 'Search', status: 'loading', search: this.state.query})
    await this.get()
    this.props.history.listen(loc => {
      if (this.mounted) {
        this.setState({query: loc.pathname.replace('/search/', '')})
        this.get()
      }
    })
  }

  componentWillUnmount () {
    this.mounted = false
  }

  async get () {
    this.props.setRootState({page_title: `Search "${decodeURIComponent(this.state.query)}"`})
    try {
      const data = await this.props.requests.get(`/search/?q=${this.state.query}`)
      if (this.mounted) {
        this.setState({items: data, loaded: true})
        this.props.setRootState({status: 'ok'})
      }
    } catch (err) {
      this.setState({error: err})
    }
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    } else if (this.state.loaded && !this.state.items.length) {
      return (
        <div className="box text-muted">
          No results for "<span className="text-dark">{decodeURIComponent(this.state.query)}</span>".
        </div>
      )
    }
    return (
      <ul className="list-group py-3 mx-0">
        {this.state.items.map((item, i) => (
          <li key={i} className="list-group-item">
            <Link to={`/people/${item.id}/`} className="d-flex justify-content-between">
              <div>
                <h6 className="my-0">{item.name}</h6>
                <div className="text-muted">
                  {item.company_name && <span>{item.company_name}</span>}
                </div>
              </div>
              <span className="float-right text-muted">{format_ts(item.last_seen)}</span>
            </Link>
          </li>
        ))}
      </ul>
    )
  }
}

export default Search
