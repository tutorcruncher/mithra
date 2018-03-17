import React, { Component } from 'react'
import {Link} from 'react-router-dom'
import Error from './Error'

class DetailsView extends Component {
  constructor (props) {
    super(props)
    this.state = {
      item: null,
      loaded: false,
      error: null,
    }
    this.url = null
    this.render_details = this.render_details.bind(this)
    this.get_url = this.get_url.bind(this)
  }

  get_url () {
    return this.url.replace(':id', this.props.id)
  }

  async componentDidMount () {
    this.props.setRootState({status: 'loading'})
    try {
      const data = await this.props.requests.get(this.get_url())
      this.setState({item: data, loaded: true})
      this.props.setRootState({status: 'ok', page_title: this.get_title(data)})
    } catch (err) {
      this.setState({error: err})
    }
  }

  get_title (data) {
    return data ? data.name : this.get_url()
  }

  render_details () {
    return (
      <pre className="mb-0 mt-1">
        <code>{JSON.stringify(this.state.item, null, 2)}</code>
      </pre>
    )
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    }
    else if (this.state.loaded && !this.state.item) {
      return (
        <div className="box">
          Item not found at <code>{this.get_url()}</code>.
        </div>
      )
    }
    return (
      <div className="box">
        {this.render_details()}
      </div>
    )
  }
}

export class Call extends DetailsView {
  constructor (props) {
    super(props)
    this.url = '/calls/:id/'
  }

  get_title (data) {
    return data.number
  }

  render_details () {
    return (
      <div>
        {
          this.state.item && this.state.item.person_id &&
          <div>
            Person:&nbsp;
            <Link to={`/people/${this.state.item.person_id}`}>{this.state.item.person_name}</Link>
          </div>
        }
        {
          this.state.item && this.state.item.company_id &&
          <div>
            Company:&nbsp;
            <Link to={`/companies/${this.state.item.company_id}`}>{this.state.item.company_name}</Link>
          </div>
        }
        {super.render_details()}
      </div>
    )
  }
}


export class Person extends DetailsView {
  constructor (props) {
    super(props)
    this.url = '/people/:id/'
  }

  render_details () {
    return (
      <div>
        {
          this.state.item && this.state.item.company_id &&
          <div>
            Company:&nbsp;
            <Link to={`/companies/${this.state.item.company_id}`}>{this.state.item.company_name}</Link>
          </div>
        }
        {super.render_details()}
      </div>
    )
  }
}

export class Company extends DetailsView {
  constructor (props) {
    super(props)
    this.url = '/companies/:id/'
  }

  render_details () {
    return (
      <div>
        {this.state.item &&
         this.state.item.login_url &&
         <a href={this.state.item.login_url} target="_blank">{this.state.item.login_url}</a>}
        {super.render_details()}
      </div>
    )
  }
}
