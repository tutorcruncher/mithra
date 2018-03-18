import React, { Component } from 'react'
import {Link, Redirect, Route, Switch, withRouter} from 'react-router-dom'
import debounce from 'lodash/debounce'
import {get, post} from '../utils'
import CallsWebSocket from '../ws'
import Calls from './Calls'
import StatusBar from './StatusBar'
import SignIn from './SignIn'
import Search from './Search'
import {People, Companies} from './ListView'
import {Call, Person, Company} from './Details'

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      page_title: null,
      status: null,
      status_alert: null,
      auth: true,
      search: '',
      ws_calls: [],
      ws_loaded: null,
      ws_error: null,
    }
    this.ws_reconnect = this.ws_reconnect.bind(this)
    this.logout = this.logout.bind(this)
    this.search_enter = this.search_enter.bind(this)
    this.search_change = this.search_change.bind(this)
    this.search_go = this.search_go.bind(this)
    this.debounce_search = debounce(this.search_go, 400)
    this.requests = {
      get: async (...args) => get(this, ...args),
      post: async (...args) => post(this, ...args),
    }
  }

  componentDidMount () {
    this.ws = new CallsWebSocket(this)
    this.props.history.listen(loc => {
      !loc.pathname.startsWith('/search/') && this.setState({search: ''})
    })
  }

  ws_reconnect () {
    this.ws.connect()
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

  search_go (v) {
    this.props.history.push(`/search/${encodeURIComponent(v)}`)
  }

  search_change (event) {
    const search = event.target.value
    this.setState({search})
    this.debounce_search(search)
  }

  async search_enter (event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      event.stopPropagation()
      this.debounce_search(this.state.search)
    }
  }

  render () {
    if (this.props.history.location.pathname !== '/signin/' && !this.state.auth) {
      return <Redirect to={{
        pathname: '/signin/',
        state: {from: this.props.location}
      }}/>
    }
    const active_nav = pathname => this.props.history.location.pathname.startsWith(pathname) && ' active'
    return (
      <div>
        <nav className="navbar navbar-expand navbar-light fixed-top bg-light">
          <div className="container">
            <Link className="navbar-brand" to="/">Mithra</Link>
            <ul className="navbar-nav mr-auto">
              <li className={`nav-item${active_nav('/people/')}`}>
                <Link className="nav-link" to="/people/">People</Link>
              </li>
              <li className={`nav-item${active_nav('/companies/')}`}>
                <Link className="nav-link" to="/companies/">Companies</Link>
              </li>
            </ul>
            <form className="form-inline">
              <input className="form-control mr-sm-2 search"
                     type="search"
                     placeholder="Search"
                     value={this.state.search}
                     onChange={this.search_change}
                     onKeyDown={this.search_enter}/>
            </form>
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
        <StatusBar title={this.state.page_title}
                   status={this.state.status}
                   alert={this.props.history.location.pathname !== '/' && this.state.status_alert}/>
        <div className="container">
          <Switch>
            <Route exact path="/" render={props => (
              <Calls history={props.history}
                     calls={this.state.ws_calls}
                     loaded={this.state.ws_loaded}
                     error={this.state.ws_error}
                     setRootState={s => this.setState(s)}/>
            )}/>
            <Route exact path="/signin/" render={props => (
              <SignIn history={props.history}
                      setRootState={s => this.setState(s)}
                      requests={this.requests}
                      ws_reconnect={this.ws_reconnect}/>
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
            <Route exact path="/search/" render={props => (
              <Search history={props.history}
                      setRootState={s => this.setState(s)}
                      requests={this.requests}
                      query=""/>
            )}/>
            <Route exact path="/search/:query/" render={props => (
              <Search history={props.history}
                      setRootState={s => this.setState(s)}
                      requests={this.requests}
                      query={props.match.params.query}/>
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
