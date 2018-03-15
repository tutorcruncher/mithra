import React, { Component } from 'react'
import {Link, Redirect, Route, Switch, withRouter} from 'react-router-dom'
import Calls from './Calls'
import StatusBar from './StatusBar'
import SignIn from './SignIn'

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      nav_title: null,
      status: null,
      auth: null,
    }
  }

  componentDidUpdate () {
    let next_title = 'Mithra'
    if (this.state.nav_title) {
      next_title += ' - ' + this.state.nav_title
    }
    if (next_title !== document.title) {
      document.title = next_title
    }
  }

  render () {
    if (this.props.history.location.pathname !== '/signin/' && this.state.auth === false) {
      return <Redirect to={{
        pathname: '/signin/',
        state: {from: this.props.location}
      }}/>
    }
    return (
      <div>
        <nav className="navbar navbar-expand-lg navbar-light fixed-top">
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
          </div>
        </nav>
        <StatusBar title={this.state.nav_title} status={this.state.status}/>
        <div className="container">
          <Switch>
            <Route exact path="/" render={props => (
              <Calls history={props.history} setRootState={s => this.setState(s)}/>
            )}/>
            <Route exact path="/signin/" render={props => (
              <SignIn history={props.history} setRootState={s => this.setState(s)}/>
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
