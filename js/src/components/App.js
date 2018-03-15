import React, { Component } from 'react'
import {Link, Redirect, Route, Switch, withRouter} from 'react-router-dom'
import {get, post} from '../utils'
import Calls from './Calls'
import StatusBar from './StatusBar'
import SignIn from './SignIn'
import {People, Companies} from './ListView'
import {Call, Person, Company} from './Details'

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      page_title: null,
      status: null,
      auth: true,
    }
    this.logout = this.logout.bind(this)
    this.requests = {
      get: async (...args) => get(this, ...args),
      post: async (...args) => post(this, ...args),
    }
  }

  componentDidUpdate () {
    let next_title = 'Mithra'
    if (this.state.page_title) {
      next_title += ' - ' + this.state.page_title
    }
    if (next_title !== document.title) {
      document.title = next_title
    }
  }

  async logout () {
    await this.requests.post('/signout/')
    this.setState({auth: false})
  }

  render () {
    if (this.props.history.location.pathname !== '/signin/' && !this.state.auth) {
      return <Redirect to={{
        pathname: '/signin/',
        state: {from: this.props.location}
      }}/>
    }
    return (
      <div>
        <nav className="navbar navbar-expand navbar-light fixed-top bg-light">
          <div className="container">
            <Link className="navbar-brand" to="/">Mithra</Link>
            <ul className="navbar-nav mr-auto">
              <li className="nav-item">
                <Link className="nav-link" to="/people/">People</Link>
              </li>
              <li className="nav-item">
                <Link className="nav-link" to="/companies/">Companies</Link>
              </li>
            </ul>
            <ul className="navbar-nav ml-auto mr-0">
              <li className="nav-item">
                <button type="button"
                        className="btn btn-link nav-link"
                        disabled={!this.state.auth}
                        onClick={() => this.logout()}>
                  Logout
                </button>
              </li>
            </ul>
          </div>
        </nav>
        <StatusBar title={this.state.page_title} status={this.state.status}/>
        <div className="container">
          <Switch>
            <Route exact path="/" render={props => (
              <Calls history={props.history} setRootState={s => this.setState(s)}/>
            )}/>
            <Route exact path="/signin/" render={props => (
              <SignIn history={props.history} setRootState={s => this.setState(s)} requests={this.requests}/>
            )}/>

            <Route exact path="/people/" render={props => (
              <People history={props.history} setRootState={s => this.setState(s)} requests={this.requests}/>
            )}/>
            <Route exact path="/companies/" render={props => (
              <Companies history={props.history} setRootState={s => this.setState(s)} requests={this.requests}/>
            )}/>

            <Route exact path="/calls/:id/" render={props => (
              <Call history={props.history}
                    setRootState={s => this.setState(s)}
                    requests={this.requests}
                    id={props.match.params.id}/>
            )}/>
            <Route exact path="/people/:id/" render={props => (
              <Person history={props.history}
                      setRootState={s => this.setState(s)}
                      requests={this.requests}
                      id={props.match.params.id}/>
            )}/>
            <Route exact path="/companies/:id/" render={props => (
              <Company history={props.history}
                       setRootState={s => this.setState(s)}
                       requests={this.requests}
                      id={props.match.params.id}/>
            )}/>

            <Route render={props => (
              <div className="box">
                <h3>Page not found</h3>
                <p>The page "{props.location.pathname}" doesn't exist.</p>
              </div>
            )}/>
          </Switch>
        </div>
      </div>
    )
  }
}

export default withRouter(_App)
